"""Gestione della sorgente, dei frame, dei comandi e del ciclo applicativo."""

from collections import Counter
from collections import deque
from datetime import datetime
import cv2
import os
import subprocess
import sys
import time
from bersagli import (
    assegna_bersagli,
    carica_poster,
    percorso_poster,
    salva_poster,
)
from configurazione import (
    ALTEZZA_CAMERA,
    ALTEZZA_VISTA_MAX,
    FRAME_SMOOTHING,
    FRECCIA_DX,
    FRECCIA_SX,
    GESTI_ATTIVI,
    LARGHEZZA_CAMERA,
    LARGHEZZA_VISTA_MAX,
    NOME_FINESTRA,
    POSTER,
    TOLLERANZA_ASSENZA,
)
from disegno import (
    in_rettangolo,
)
from eventi import (
    Eventi,
    fmt_orologio,
    fmt_video,
)
from geometria import (
    direzione,
)
from interfaccia import (
    Interfaccia,
)
from rilevamento import (
    analizza,
    mp_hands,
    mp_pose,
)
from stile import (
    FONT_GRASSETTO,
    FONT_MONO,
    carica_font,
)


# ------------------------- Scelta del file video --------------------------
def scegli_file_video():
    """Apre la finestra di scelta file del sistema. Restituisce il percorso o None."""
    try:
        if sys.platform == "darwin":
            script = ('tell me to activate\n'
                      'POSIX path of (choose file with prompt "Scegli un video" '
                      'of type {"avi","mp4","mov","mkv","m4v","mpg","mpeg","wmv"})')
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        else:
            codice = ("import tkinter as tk; from tkinter import filedialog; "
                      "r = tk.Tk(); r.withdraw(); "
                      "print(filedialog.askopenfilename(title='Scegli un video', "
                      "filetypes=[('Video', '*.avi *.mp4 *.mov *.mkv *.m4v'), ('Tutti i file', '*.*')]))")
            r = subprocess.run([sys.executable, "-c", codice], capture_output=True, text=True)
        percorso = r.stdout.strip()
        return percorso if (r.returncode == 0 and percorso) else None
    except Exception as errore:  # noqa: BLE001
        print(f"Impossibile aprire la finestra di scelta file: {errore}")
        return None

class App(Interfaccia):
    """Coordina rilevamento, bersagli, eventi e visualizzazione."""

    def __init__(self, args):
        self.args = args
        self.ui = {"pulsanti": [], "hover": None, "azione": None, "barra": None,
                   "calibra": False, "vista": None}
        self.F = {
            "h1": carica_font(56, FONT_GRASSETTO),
            "testata": carica_font(18, FONT_GRASSETTO),
            "titolo": carica_font(16, FONT_GRASSETTO),
            "stato": carica_font(17, FONT_GRASSETTO),
            "azione": carica_font(17, FONT_GRASSETTO),
            "sottotitolo": carica_font(18),
            "testo": carica_font(14),
            "piccolo": carica_font(12),
            "etichetta": carica_font(12, FONT_GRASSETTO),
            "btn": carica_font(13, FONT_GRASSETTO),
            "mono": carica_font(12, FONT_MONO),
        }
        self.pose = mp_pose.Pose(static_image_mode=False, model_complexity=args.pose,
                                 smooth_landmarks=True, min_detection_confidence=0.5,
                                 min_tracking_confidence=0.5)
        self.hands_rit = mp_hands.Hands(static_image_mode=True, max_num_hands=1,
                                        min_detection_confidence=0.4)
        self.hands_pieno = mp_hands.Hands(static_image_mode=False, max_num_hands=2,
                                          model_complexity=1, min_detection_confidence=0.6,
                                          min_tracking_confidence=0.6)
        # mani cercate in una zona ingrandita attorno a tutta la persona
        self.hands_roi = mp_hands.Hands(static_image_mode=True, max_num_hands=2,
                                        min_detection_confidence=0.35)
        self.sorg = None
        self.eventi = None
        self.nome_csv = None
        self.stato = {}
        self.scena = None
        self.writer = None
        self.indice = 0
        self.ultimo_t = 0.0
        self.fps = 0.0
        self.t_prec = time.time()
        self.in_pausa = False
        self.forza_lettura = False
        self.finito = False
        self.riepilogo_stampato = False
        self.tracciamento = False
        self.passo_esatto = False   # prossima lettura: esattamente il frame successivo
        self.bersagli = {}          # poster segnati: {nome: (x, y)} normalizzati
        self.calibra = None         # stato della calibrazione dei poster, se in corso
        self.path_poster = None
        self.messaggio = None
        self.esci = False

        cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(NOME_FINESTRA, self._mouse, self.ui)

    @staticmethod
    def _mouse(evento, x, y, flags, ui):
        if evento not in (cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONDOWN):
            return
        clic = evento == cv2.EVENT_LBUTTONDOWN
        ui["hover"] = None
        for pid, rect in ui["pulsanti"]:
            if in_rettangolo(x, y, rect):
                ui["hover"] = pid
                if clic:
                    ui["azione"] = (pid, None)
                return
        barra = ui["barra"]
        if barra and in_rettangolo(x, y, barra):
            ui["hover"] = "seek"
            if clic:
                ui["azione"] = ("seek", (x - barra[0]) / (barra[2] - barra[0] - 1))
            return
        vista = ui["vista"]
        if clic and ui["calibra"] and vista and in_rettangolo(x, y, vista):
            ui["azione"] = ("clic_poster", (x, y))

    def msg(self, testo, secondi=7):
        print(testo)
        self.messaggio = (testo, time.time() + secondi)

    def _msg_attivo(self):
        if self.messaggio and time.time() < self.messaggio[1]:
            return self.messaggio[0]
        self.messaggio = None
        return None

    def _reset_rilevatori(self):
        for oggetto in (self.pose, self.hands_rit, self.hands_pieno, self.hands_roi):
            try:
                oggetto.reset()
            except Exception:  # noqa: BLE001
                pass

    def avvia_video(self, percorso):
        if not os.path.isfile(percorso):
            self.msg(f"File non trovato: {percorso}")
            return
        cap = cv2.VideoCapture(percorso)
        if not cap.isOpened():
            self.msg("Impossibile aprire il video. Se è un .mkv di Azure Kinect, convertilo con ffmpeg.")
            return
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps != fps or fps < 1 or fps > 240:
            fps = 30.0
        totale = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        sorg = {
            "tipo": "video", "cap": cap, "fps": fps, "totale": totale,
            "durata": totale / fps if totale > 0 else 0.0,
            "nome": os.path.basename(percorso), "percorso": percorso,
            "specchio": False, "pose": self.args.rilevamento != "mani", "fmt": fmt_video,
        }
        stem = os.path.splitext(os.path.basename(percorso))[0]
        print(f"Video: {percorso}  ({fps:.1f} fps, durata {fmt_video(sorg['durata'])})")
        self._avvia(sorg, f"registro_{stem}.csv")

    def avvia_webcam(self):
        cap = cv2.VideoCapture(self.args.camera)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, LARGHEZZA_CAMERA)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTEZZA_CAMERA)
        if not cap.isOpened():
            self.msg("Webcam non disponibile. Controlla il permesso Fotocamera in Impostazioni di Sistema.")
            return
        sorg = {
            "tipo": "webcam", "cap": cap, "fps": 30.0, "totale": 0, "durata": 0.0,
            "nome": "Webcam", "percorso": None, "specchio": True,
            "pose": self.args.rilevamento != "mani", "fmt": fmt_orologio,
        }
        self._avvia(sorg, datetime.now().strftime("registro_webcam_%Y%m%d_%H%M%S.csv"))

    def _avvia(self, sorg, nome_csv):
        self.chiudi_sorgente()
        self.sorg = sorg
        self.nome_csv = None if self.args.nessun_csv else nome_csv
        self.eventi = Eventi(self.nome_csv, sorg["fmt"])
        self.stato = {}
        self.scena = None
        self.indice = 0
        self.ultimo_t = 0.0
        self.fps = 0.0
        self.t_prec = time.time()
        self.in_pausa = False
        self.finito = False
        self.forza_lettura = False
        self.riepilogo_stampato = False
        self.writer = None
        self.messaggio = None
        self._reset_rilevatori()
        self.calibra = None
        self.ui["calibra"] = False
        self.ui["hover"] = None
        self.path_poster = percorso_poster(sorg)
        self.bersagli = carica_poster(self.path_poster)
        if self.bersagli:
            self.msg("Poster caricati: " + ", ".join(self.bersagli), 4)

    def _chiudi_eventi_aperti(self):
        if self.eventi is None:
            return
        for nome in list(self.stato):
            self.eventi.cambia(nome, self.stato[nome], None, self.stato[nome]["ultimo_visto"])
        self.stato = {}

    def chiudi_sorgente(self):
        if self.sorg is None:
            return
        self._chiudi_eventi_aperti()
        if self.eventi is not None:
            if not self.riepilogo_stampato:
                self.eventi.riepilogo()
            self.eventi.chiudi()
        if self.writer is not None:
            self.writer.release()
        self.sorg["cap"].release()
        self.sorg = None
        self.eventi = None
        self.scena = None
        self.writer = None
        self.calibra = None
        self.ui["calibra"] = False

    def apri_dialogo(self):
        cv2.waitKey(1)
        percorso = scegli_file_video()
        cv2.waitKey(1)
        if percorso:
            self.avvia_video(percorso)

    def toggle_pausa(self):
        if self.sorg is None:
            return
        if self.finito:
            self._riavvia_video()
        else:
            self.in_pausa = not self.in_pausa

    def _riavvia_video(self):
        self.eventi.chiudi()
        self.eventi = Eventi(self.nome_csv, self.sorg["fmt"])
        self.stato = {}
        self.indice = 0
        self.ultimo_t = 0.0
        self.finito = False
        self.in_pausa = False
        self.riepilogo_stampato = False
        self.sorg["cap"].set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._reset_rilevatori()

    def _cerca(self, frazione):
        s = self.sorg
        if not s or s["tipo"] != "video" or s["totale"] <= 0:
            return
        self._chiudi_eventi_aperti()
        n = int(max(0, min(s["totale"] - 1, frazione * s["totale"])))
        s["cap"].set(cv2.CAP_PROP_POS_FRAMES, n)
        self.indice = n
        self.finito = False
        self.riepilogo_stampato = False
        self.forza_lettura = True
        self._reset_rilevatori()

    def _fine_video(self):
        self._chiudi_eventi_aperti()
        self.eventi.riepilogo()
        self.riepilogo_stampato = True
        self.finito = True
        self.in_pausa = True
        self.msg("Fine del video. Premi «Ricomincia» per rivederlo dall’inizio.")

    def avvia_calibrazione(self):
        """Il video torna all'inizio e si segnano a mano i poster con un clic ciascuno."""
        if self.calibra is not None:
            self._annulla_calibrazione()
            return
        if self.sorg is None:
            self.msg("Apri prima un video o la webcam, poi segna i poster.")
            return
        if self.sorg["tipo"] == "video":
            self._cerca(0.0)
        self.in_pausa = True
        self.calibra = {"i": 0, "tmp": {}}
        self.ui["calibra"] = True

    def _annulla_calibrazione(self):
        self.calibra = None
        self.ui["calibra"] = False
        self.msg("Calibrazione annullata.", 3)

    def _clic_poster(self, x, y):
        c, vista = self.calibra, self.ui.get("vista")
        if c is None or vista is None or not in_rettangolo(x, y, vista):
            return
        x1, y1, x2, y2 = vista
        c["tmp"][POSTER[c["i"]]] = ((x - x1) / (x2 - x1), (y - y1) / (y2 - y1))
        self._avanza_calibrazione()

    def _avanza_calibrazione(self):
        c = self.calibra
        if c is None:
            return
        c["i"] += 1
        if c["i"] < len(POSTER):
            return
        self.bersagli = dict(c["tmp"])
        self.calibra = None
        self.ui["calibra"] = False
        if self.path_poster:
            salvato = salva_poster(self.path_poster, self.bersagli)
            nota = f" (salvati in {os.path.basename(self.path_poster)})" if salvato else " (non salvati su file)"
        else:
            nota = ""
        self.msg(("Poster segnati: " + ", ".join(self.bersagli) if self.bersagli
                  else "Nessun poster segnato") + nota, 5)

    def _passo_frame(self, delta):
        """Un frame avanti (+1) o indietro (-1), solo sui video. Mette in pausa."""
        s = self.sorg
        if s is None:
            return
        if s["tipo"] != "video":
            self.msg("Il passo frame funziona solo sui video.", 3)
            return
        self.in_pausa = True
        self.passo_esatto = True
        if delta > 0:
            if not self.finito:
                self.forza_lettura = True   # legge il frame successivo
            return
        # indietro: il frame mostrato e' self.indice - 1
        nuovo = max(0, self.indice - 1 + delta)
        self._chiudi_eventi_aperti()
        s["cap"].set(cv2.CAP_PROP_POS_FRAMES, nuovo)
        self.indice = nuovo
        self.finito = False
        self.riepilogo_stampato = False
        self.forza_lettura = True
        self._reset_rilevatori()

    def _leggi_e_analizza(self):
        s = self.sorg
        cap = s["cap"]
        ogni = 1 if self.passo_esatto else max(1, self.args.ogni)
        self.passo_esatto = False
        if s["tipo"] == "video" and ogni > 1:
            while self.indice % ogni != 0:
                if not cap.grab():
                    return False
                self.indice += 1
        ok, frame = cap.read()
        if not ok:
            return False
        t = (self.indice / s["fps"]) if s["tipo"] == "video" else time.time()
        self.indice += 1
        self.ultimo_t = t if s["tipo"] == "video" else (t - self.t_inizio_webcam())

        if s["specchio"]:
            frame = cv2.flip(frame, 1)
        H, W = frame.shape[:2]

        record, corpo = analizza(frame, self.pose if s["pose"] else None, self.hands_rit,
                                 self.hands_pieno, self.hands_roi, s["specchio"])
        bersagli_px = {n: (p[0] * W, p[1] * H) for n, p in self.bersagli.items()}
        assegna_bersagli(record, bersagli_px, self.args.solo_poster, self.args.tolleranza_poster)
        self._aggiorna_stati(record, t)

        # Mantiene la risoluzione di esportazione, separata dall'anteprima dell'interfaccia.
        k = min(1.0, LARGHEZZA_VISTA_MAX / W, ALTEZZA_VISTA_MAX / H)
        formato = (max(1, int(W * k)), max(1, int(H * k)))
        base = cv2.resize(frame, formato, interpolation=cv2.INTER_AREA) if k < 1 else frame

        attivo = (next((r for r in record if r["gesto"] == "Pointing"), None)
                  or next((r for r in record if r["gesto"] == "Braccio teso"), None))
        self.scena = {"base": base, "dimensioni": (W, H), "corpo": corpo,
                      "record": record, "attivo": attivo}
        return True

    def t_inizio_webcam(self):
        if not hasattr(self, "_t0_webcam") or self._t0_webcam_sorg is not self.sorg:
            self._t0_webcam = time.time()
            self._t0_webcam_sorg = self.sorg
        return self._t0_webcam

    def _aggiorna_stati(self, record, t):
        viste = set()
        for r in record:
            nome = r["nome"]
            viste.add(nome)
            s = self.stato.setdefault(nome, {"storico": deque(maxlen=FRAME_SMOOTHING),
                                             "storico_bers": deque(maxlen=FRAME_SMOOTHING),
                                             "gesto": None, "bersaglio": "",
                                             "inizio": 0.0, "direz": "", "assente": 0,
                                             "ultimo_visto": t})
            s["assente"] = 0
            s["ultimo_visto"] = t
            s["storico"].append(r["gesto"])
            stabile = Counter(s["storico"]).most_common(1)[0][0]
            r["gesto"] = stabile
            r["direz"] = ""
            bers = ""
            if stabile in GESTI_ATTIVI:
                r["direz"] = direzione(r["punta"][0] - r["base"][0], r["punta"][1] - r["base"][1])
                s["storico_bers"].append(r.get("bersaglio") or "")
                bers = Counter(s["storico_bers"]).most_common(1)[0][0]
            else:
                s["storico_bers"].clear()
            r["bersaglio"] = bers
            evento = stabile if stabile in GESTI_ATTIVI else None
            if evento != s["gesto"] or (evento and bers != s.get("bersaglio", "")):
                self.eventi.cambia(nome, s, evento, t, r["direz"], r["braccio"], bers)

        for nome in list(self.stato):
            if nome not in viste:
                self.stato[nome]["assente"] += 1
                if self.stato[nome]["assente"] > TOLLERANZA_ASSENZA:
                    self.eventi.cambia(nome, self.stato[nome], None, self.stato[nome]["ultimo_visto"])
                    del self.stato[nome]

    def _passo_riproduzione(self):
        nuovo = False
        if (not self.in_pausa or self.forza_lettura) and not self.finito:
            self.forza_lettura = False
            if self._leggi_e_analizza():
                nuovo = True
                adesso = time.time()
                ist = 1.0 / max(adesso - self.t_prec, 1e-3)
                self.fps = ist if self.fps == 0 else self.fps * 0.9 + ist * 0.1
                self.t_prec = adesso
            elif self.scena is None:
                self.msg("Non riesco a leggere le immagini da questa sorgente.")
                self.chiudi_sorgente()
                return self._render_home()
            elif self.sorg["tipo"] == "video":
                self._fine_video()
            else:
                self.msg("La webcam ha smesso di rispondere.")
                self.chiudi_sorgente()
                return self._render_home()

        if self.args.salva_video and nuovo:
            img = self._componi_video()
            if self.writer is None:
                base = os.path.splitext(self.sorg["percorso"])[0] if self.sorg["percorso"] \
                    else datetime.now().strftime("webcam_%Y%m%d_%H%M%S")
                nome_out = base + "_annotato.mp4"
                fps_out = (self.sorg["fps"] / max(1, self.args.ogni)) if self.sorg["tipo"] == "video" else 20.0
                self.writer = cv2.VideoWriter(nome_out, cv2.VideoWriter_fourcc(*"mp4v"), fps_out,
                                              (img.shape[1], img.shape[0]))
                print(f"Salvo il video annotato in: {nome_out}")
            self.writer.write(img)

        return self._render_riproduzione()

    def _gestisci_azione(self):
        azione = self.ui["azione"]
        self.ui["azione"] = None
        if azione is None:
            return
        pid, valore = azione
        if pid == "apri_video":
            self.apri_dialogo()
        elif pid == "webcam":
            self.avvia_webcam()
        elif pid == "pausa":
            self.toggle_pausa()
        elif pid == "poster":
            self.avvia_calibrazione()
        elif pid == "clic_poster":
            self._clic_poster(*valore)
        elif pid == "frame_ind":
            self._passo_frame(-1)
        elif pid == "frame_avanti":
            self._passo_frame(+1)
        elif pid == "tracciamento":
            self.tracciamento = not self.tracciamento
        elif pid == "esci":
            self.esci = True
        elif pid == "seek":
            self._cerca(valore)

    def _gestisci_tasto(self, tasto, raw=-1):
        if self.calibra is not None:
            if tasto == 27:
                self._annulla_calibrazione()
                return
            if tasto in (13, 10):
                self._avanza_calibrazione()
                return
        if tasto in (ord("q"), 27):
            self.esci = True
        elif tasto == ord("o"):
            self.apri_dialogo()
        elif tasto == ord("w"):
            self.avvia_webcam()
        elif tasto == ord(" "):
            self.toggle_pausa()
        elif tasto == ord("t"):
            self.tracciamento = not self.tracciamento
        elif tasto == ord("p"):
            self.avvia_calibrazione()
        elif tasto in (ord("d"), ord(".")) or raw in FRECCIA_DX:
            self._passo_frame(+1)
        elif tasto in (ord("a"), ord(",")) or raw in FRECCIA_SX:
            self._passo_frame(-1)

    def esegui(self):
        try:
            while not self.esci:
                self._gestisci_azione()
                img = self._render_home() if self.sorg is None else self._passo_riproduzione()
                cv2.imshow(NOME_FINESTRA, img)
                in_riproduzione = self.sorg is not None and not self.in_pausa
                raw = cv2.waitKeyEx(1 if in_riproduzione else 30)
                self._gestisci_tasto(raw & 0xFF, raw)
                if cv2.getWindowProperty(NOME_FINESTRA, cv2.WND_PROP_VISIBLE) < 1:
                    break
        except KeyboardInterrupt:
            print("\nInterrotto con Ctrl+C.")
        finally:
            self.chiudi_sorgente()
            for oggetto in (self.pose, self.hands_rit, self.hands_pieno, self.hands_roi):
                try:
                    oggetto.close()
                except Exception:  # noqa: BLE001
                    pass
            cv2.destroyAllWindows()
