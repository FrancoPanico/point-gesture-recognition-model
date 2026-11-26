"""Metodi di visualizzazione dell’applicazione."""

import cv2
import math
import numpy as np
from configurazione import (
    GESTI_ATTIVI,
    NOME_FINESTRA,
    POSTER,
)
from disegno import (
    disegna_angoli,
    disegna_arto,
    disegna_bussola,
    disegna_corpo,
    disegna_icona,
    disegna_raggio,
    disegna_scheletro,
    disegna_testi,
    due_righe,
    etichetta_frame,
    rett_arrotondato,
    riquadro,
    scala_punto,
    scheda,
    schiarisci,
    tronca,
)
from eventi import (
    fmt_breve,
    fmt_video,
)
from stile import (
    ACCENTO,
    ALTEZZA_TESTATA,
    ALTEZZA_UI,
    AMBRA,
    BORDO,
    BORDO_SELEZIONATO,
    FONDO_ACCENTO,
    FONDO_AMBRA,
    FONDO_VIDEO,
    GRIGLIA,
    LARGHEZZA_UI,
    MARGINE_UI,
    OMBRA,
    PANNELLO,
    PANNELLO_EVENTI,
    PANNELLO_RILEVAMENTO,
    PANNELLO_VIDEO,
    PRIMARIO,
    ROSSO_LIVE,
    SECONDARIO,
    SELEZIONATO,
    SFONDO,
    TESTO,
    TESTO_DIM,
    TESTO_SCURO,
    TESTO_SEC,
    TRACCIAMENTO,
    VANO_VIDEO,
)


class Interfaccia:
    """Metodi grafici ereditati da App; utilizzano lo stato della stessa finestra."""

    def _disegna_record(self, img, testi, record, scala):
        h, w = img.shape[:2]
        font = self.F["etichetta"]
        alt_font = getattr(font, "size", 12)
        for r in record:
            attivo = r["gesto"] in GESTI_ATTIVI
            if not attivo and not self.tracciamento:
                continue

            colore = TRACCIAMENTO
            if attivo:
                colore = ACCENTO if r["gesto"] == "Pointing" else AMBRA

            pts = [scala_punto(p, scala) for p in r["pts"]] if r["pts"] is not None else []
            arto = [scala_punto(p, scala) for p in r["arto"]] if r["arto"] is not None else []
            if arto:
                disegna_arto(img, *arto, colore, sottile=not attivo)
            if pts:
                disegna_scheletro(img, pts, colore, sottile=not attivo)
            if not attivo:
                continue

            disegna_raggio(img, scala_punto(r["base"], scala), scala_punto(r["punta"], scala), colore)
            if pts or arto:
                box = riquadro(pts or arto[-1:], w, h, margine=15 if pts else 23)
                x1, y1, _, y2 = box
                y_tag = y1 - alt_font - 12 if y1 > alt_font + 15 else y2 + 5
                disegna_angoli(img, box, colore)
                etichetta_frame(img, testi, x1, y_tag, f"{r['gesto']} · {r['nome'].lower()}", font, colore)

    def _disegna_bersagli(self, img, testi, bersagli, attivo):
        h, w = img.shape[:2]
        for nome, (nx, ny) in bersagli.items():
            if not (0 <= nx <= 1 and 0 <= ny <= 1):
                continue
            x, y = min(w - 1, round(nx * w)), min(h - 1, round(ny * h))
            colore = self._stato_gesto(attivo)[1] if attivo and nome == attivo.get("bersaglio") else TESTO
            cv2.circle(img, (x, y), 10, OMBRA, 4, cv2.LINE_AA)
            cv2.circle(img, (x, y), 10, colore, 1, cv2.LINE_AA)
            cv2.circle(img, (x, y), 2, colore, -1, cv2.LINE_AA)
            etichetta_frame(img, testi, x + 15, y - 10, nome, self.F["etichetta"], colore)

    def _fotogramma_annotato(self, w, h, bersagli):
        sc = self.scena
        base = sc["base"]
        if base.shape[:2] == (h, w):
            img = base.copy()
        else:
            inter = cv2.INTER_AREA if w < base.shape[1] else cv2.INTER_LINEAR
            img = cv2.resize(base, (w, h), interpolation=inter)
        W, H = sc["dimensioni"]
        scala = (w / W, h / H)
        testi = []
        disegna_corpo(img, sc["corpo"], scala)
        self._disegna_record(img, testi, sc["record"], scala)
        self._disegna_bersagli(img, testi, bersagli, sc["attivo"])
        return disegna_testi(img, testi)

    @staticmethod
    def _stato_gesto(attivo):
        if attivo is None:
            return "Nessun pointing", TESTO_DIM, SECONDARIO
        if attivo["gesto"] == "Pointing":
            return "Pointing rilevato", ACCENTO, FONDO_ACCENTO
        return "Braccio teso", AMBRA, FONDO_AMBRA

    def _componi_video(self):
        """Esporta il fotogramma annotato alla risoluzione di prima."""
        h, w = self.scena["base"].shape[:2]
        img = self._fotogramma_annotato(w, h, self.bersagli)
        if w < 190 or h < 112:
            return img

        F = self.F
        testi = []
        attivo = self.scena["attivo"]
        titolo, colore, _ = self._stato_gesto(attivo)
        nome = self.sorg["nome"]
        if attivo is not None:
            meta = f"Mano {attivo['nome'].lower()} · {attivo.get('bersaglio') or attivo['direz']}"
            nome = f"{meta}  /  {nome}"
        scheda(img, (10, 10, w - 11, 61), raggio=8)
        cv2.circle(img, (23, 27), 3, colore, -1, cv2.LINE_AA)
        testi.append((34, 27, titolo, F["testo"], TESTO, "lm"))
        if w >= 280:
            testi.append((w - 21, 27, f"{self.fps:.0f} FPS", F["mono"], TESTO_SEC, "rm"))
        testi.append((21, 46, tronca(nome, F["piccolo"], w - 42), F["piccolo"], TESTO_SEC, "lm"))

        if h >= 178 and w >= 270:
            ev = list(self.eventi.recenti)[-min(5, (h - 111) // 19):]
            if ev:
                larg = min(w - 94, max(math.ceil(F["piccolo"].getlength(e)) for e in ev) + 24)
                y = h - 11 - 33 - 19 * len(ev)
                scheda(img, (10, y, 10 + larg, h - 11), raggio=8)
                testi.append((22, y + 15, "Eventi recenti", F["etichetta"], TESTO, "lm"))
                for i, e in enumerate(ev):
                    riga = tronca(e, F["piccolo"], larg - 24)
                    testi.append((22, y + 35 + 19 * i, riga, F["piccolo"], TESTO_SEC, "lm"))
            if attivo is not None:
                centro = (w - 37, h - 36)
                cv2.circle(img, centro, 25, PANNELLO, -1, cv2.LINE_AA)
                disegna_bussola(img, centro, 18, attivo["direz"], colore)
        return disegna_testi(img, testi)

    def _tasto(self, img, testi, x, y, tasto):
        font = self.F["mono"]
        larg = math.ceil(font.getlength(tasto)) + 14
        scheda(img, (x, y - 12, x + larg, y + 12), SFONDO, BORDO, 5)
        testi.append((x + larg // 2, y, tasto, font, TESTO_SEC, "mm"))
        return larg

    def _pulsante(self, img, testi, pid, rect, etichetta, simbolo, *,
                  primario=False, attivo=False, abilitato=True, tasto=None):
        x1, y1, x2, y2 = rect
        fill, bordo, colore = SECONDARIO, BORDO, TESTO
        if not abilitato:
            fill, colore = PANNELLO, TESTO_DIM
        elif primario:
            fill, bordo, colore = PRIMARIO, PRIMARIO, TESTO_SCURO
        elif attivo:
            fill, bordo, colore = SELEZIONATO, BORDO_SELEZIONATO, PRIMARIO
        if abilitato and self.ui["hover"] == pid:
            fill, bordo = schiarisci(fill, 13), schiarisci(bordo, 16)

        scheda(img, rect, fill, bordo, 9)
        yc = (y1 + y2) // 2
        if tasto:
            font = self.F["azione"]
            rett_arrotondato(img, (x1 + 14, yc - 16), (x1 + 46, yc + 16),
                             TESTO if primario else SELEZIONATO, 7)
            disegna_icona(img, simbolo, x1 + 30, yc, TESTO_SCURO if primario else PRIMARIO)
            testi.append((x1 + 58, yc, etichetta, font, colore, "lm"))
            larg = math.ceil(self.F["mono"].getlength(tasto)) + 14
            self._tasto(img, testi, x2 - larg - 14, yc, tasto)
        else:
            font = self.F["btn"]
            x = (x1 + x2 - math.ceil(font.getlength(etichetta)) - 23) // 2
            disegna_icona(img, simbolo, x + 7, yc, colore)
            testi.append((x + 23, yc, etichetta, font, colore, "lm"))
        if abilitato:
            self.ui["pulsanti"].append((pid, rect))

    def _testata(self, img, testi, riproduzione):
        x, y = MARGINE_UI, ALTEZZA_TESTATA // 2
        img[:ALTEZZA_TESTATA] = PANNELLO
        cv2.line(img, (0, ALTEZZA_TESTATA), (LARGHEZZA_UI, ALTEZZA_TESTATA), BORDO, 1)
        scheda(img, (x, y - 16, x + 32, y + 16), SELEZIONATO, BORDO, 8)
        cv2.arrowedLine(img, (x + 10, y + 6), (x + 23, y - 7), PRIMARIO, 2, cv2.LINE_AA, 0, 0.38)
        destra = LARGHEZZA_UI - MARGINE_UI
        if riproduzione:
            testi.append((x + 45, y, NOME_FINESTRA, self.F["testata"], TESTO, "lm"))
            self._pulsante(img, testi, "apri_video", (destra - 312, y - 18, destra - 195, y + 18),
                           "Apri video", "video")
            self._pulsante(img, testi, "webcam", (destra - 186, y - 18, destra - 83, y + 18),
                           "Webcam", "webcam")
        self._pulsante(img, testi, "esci", (destra - 74, y - 18, destra, y + 18), "Esci", "esci")

    def _notifica(self, img, testi, rect, messaggio, scorciatoie=""):
        x1, y1, x2, y2 = rect
        yc = (y1 + y2) // 2
        font = self.F["testo"]
        scheda(img, rect, SELEZIONATO, BORDO, 7)
        disegna_icona(img, "info", x1 + 17, yc, PRIMARIO)
        spazio = x2 - x1 - 46
        if scorciatoie:
            spazio -= math.ceil(self.F["piccolo"].getlength(scorciatoie)) + 14
            testi.append((x2 - 12, yc, scorciatoie, self.F["piccolo"], TESTO_SEC, "rm"))
        if y2 - y1 >= 49:
            righe = due_righe(messaggio, font, spazio)
        else:
            righe = (tronca(messaggio, font, spazio),)
        for i, riga in enumerate(righe):
            testi.append((x1 + 33, yc + 17 * i - 8 * (len(righe) - 1), riga, font, TESTO, "lm"))

    def _disegna_sorgente(self, img, testi):
        x1, y1, x2, _ = PANNELLO_VIDEO
        y = (y1 + VANO_VIDEO[1]) // 2
        rect = (x1 + 9, y1 + 6, x2 - 9, VANO_VIDEO[1] - 6)
        if self.calibra is not None:
            poster = POSTER[self.calibra["i"]]
            self._notifica(img, testi, rect, f"Clicca al centro del poster «{poster}»",
                           "Invio salta   ·   Esc annulla")
            return
        messaggio = self._msg_attivo()
        if messaggio:
            self._notifica(img, testi, rect, messaggio)
            return

        webcam = self.sorg["tipo"] == "webcam"
        if self.finito:
            stato, colore = "Fine video", TESTO_SEC
        elif self.in_pausa:
            stato, colore = "In pausa", AMBRA
        elif webcam:
            stato, colore = "In diretta", ROSSO_LIVE
        else:
            stato, colore = "In riproduzione", PRIMARIO
        F = self.F
        fps = f"{self.fps:.0f} FPS" if self.fps else "— FPS"
        x_fps = x2 - 17
        x_stato = x_fps - math.ceil(F["mono"].getlength(fps)) - 26
        x_dot = x_stato - math.ceil(F["piccolo"].getlength(stato)) - 10
        nome = tronca(self.sorg["nome"], F["testo"], x_dot - x1 - 63)
        disegna_icona(img, "webcam" if webcam else "video", x1 + 23, y, TESTO_SEC)
        testi.append((x1 + 41, y, nome, F["testo"], TESTO, "lm"))
        cv2.circle(img, (x_dot, y), 3, colore, -1, cv2.LINE_AA)
        testi.append((x_stato, y, stato, F["piccolo"], TESTO_SEC, "rm"))
        cv2.line(img, (x_stato + 13, y - 9), (x_stato + 13, y + 9), BORDO, 1)
        testi.append((x_fps, y, fps, F["mono"], TESTO_SEC, "rm"))

    def _disegna_controlli(self, img, testi):
        x1, _, x2, y2 = PANNELLO_VIDEO
        sx, dx = x1 + 18, x2 - 18
        y_t = VANO_VIDEO[3] + 26
        s = self.sorg
        F = self.F

        self.ui["barra"] = None
        if s["tipo"] == "video":
            tempo = fmt_video(self.ultimo_t)
            frame = f"Frame {max(0, self.indice - 1)}"
            x_frame = dx - math.ceil(F["mono"].getlength(frame))
            testi.append((dx, y_t, frame, F["mono"], TESTO_SEC, "rm"))
            testi.append((sx, y_t, tempo, F["mono"], TESTO, "lm"))
            if s["durata"] > 0:
                durata = fmt_video(s["durata"])
                x_durata = x_frame - 25
                a = sx + math.ceil(F["mono"].getlength(tempo)) + 18
                b = x_durata - math.ceil(F["mono"].getlength(durata)) - 18
                cv2.line(img, (x_frame - 13, y_t - 8), (x_frame - 13, y_t + 8), BORDO, 1)
                testi.append((x_durata, y_t, durata, F["mono"], TESTO_SEC, "rm"))

                frac = 1.0 if self.finito else max(0.0, min(1.0, self.ultimo_t / s["durata"]))
                punto = round(a + (b - a) * frac)
                hover = self.ui["hover"] == "seek"
                cv2.line(img, (a, y_t), (b, y_t), BORDO, 5 if hover else 4, cv2.LINE_AA)
                cv2.line(img, (a, y_t), (punto, y_t), PRIMARIO, 4, cv2.LINE_AA)
                cv2.circle(img, (punto, y_t), 6 if hover else 5, TESTO, -1, cv2.LINE_AA)
                self.ui["barra"] = (a, y_t - 12, b + 1, y_t + 13)
        else:
            testi.append((sx, y_t, "Tempo trascorso", F["piccolo"], TESTO_SEC, "lm"))
            testi.append((sx + 114, y_t, fmt_breve(self.ultimo_t), F["mono"], TESTO, "lm"))

        y, fine = y2 - 54, y2 - 16
        pausa = "Ricomincia" if self.finito else "Riprendi" if self.in_pausa else "Pausa"
        simbolo = "riprendi" if self.in_pausa else "pausa"
        video = s["tipo"] == "video"
        self._pulsante(img, testi, "pausa", (sx, y, sx + 126, fine), pausa, simbolo, primario=True)
        self._pulsante(img, testi, "frame_ind", (sx + 136, y, sx + 232, fine),
                       "Frame −1", "prima", abilitato=video)
        self._pulsante(img, testi, "frame_avanti", (sx + 240, y, sx + 336, fine),
                       "Frame +1", "dopo", abilitato=video)
        cv2.line(img, (dx - 242, y + 6), (dx - 242, fine - 6), BORDO, 1)
        self._pulsante(img, testi, "tracciamento", (dx - 229, y, dx - 93, fine),
                       "Tracciamento", "traccia", attivo=self.tracciamento)
        self._pulsante(img, testi, "poster", (dx - 84, y, dx, fine),
                       "Poster", "poster", attivo=self.calibra is not None)

    def _disegna_rilevamento(self, img, testi):
        x1, y1, x2, _ = PANNELLO_RILEVAMENTO
        sx, dx = x1 + 18, x2 - 18
        F = self.F
        scheda(img, PANNELLO_RILEVAMENTO)
        testi.append((sx, y1 + 25, "Rilevamento", F["titolo"], TESTO, "lm"))
        cv2.line(img, (sx, y1 + 48), (dx, y1 + 48), BORDO, 1)

        attivo = self.scena["attivo"]
        titolo, colore, fondo = self._stato_gesto(attivo)
        rett_arrotondato(img, (sx, y1 + 61), (dx, y1 + 106), fondo, 8)
        probabile = attivo is not None and attivo["gesto"] == "Braccio teso"
        y_t = y1 + (77 if probabile else 83)
        cv2.circle(img, (sx + 13, y_t), 3, colore, -1, cv2.LINE_AA)
        testi.append((sx + 26, y_t, titolo, F["stato"], colore, "lm"))
        if probabile:
            testi.append((sx + 26, y1 + 94, "Probabile pointing", F["piccolo"], TESTO_SEC, "lm"))

        mano = attivo["nome"] if attivo else "—"
        bersaglio = (attivo.get("bersaglio") or "—") if attivo else "—"
        direz = attivo["direz"] if attivo else ""
        for y, etichetta, valore in ((y1 + 128, "Mano", mano), (y1 + 154, "Bersaglio", bersaglio)):
            testi.append((sx, y, etichetta, F["testo"], TESTO_SEC, "lm"))
            testi.append((dx, y, valore, F["testo"], TESTO, "rm"))

        cv2.line(img, (sx, y1 + 174), (dx, y1 + 174), BORDO, 1)
        testi.append((sx, y1 + 190, "Direzione", F["piccolo"], TESTO_SEC, "lm"))
        testi.append((sx, y1 + 211, direz.capitalize() or "—", F["testo"], TESTO, "lm"))
        disegna_bussola(img, (dx - 22, y1 + 201), 16, direz, colore)

    def _disegna_eventi(self, img, testi):
        x1, y1, x2, _ = PANNELLO_EVENTI
        sx, dx = x1 + 18, x2 - 18
        F = self.F
        scheda(img, PANNELLO_EVENTI)
        testi.append((sx, y1 + 25, "Eventi recenti", F["titolo"], TESTO, "lm"))
        cv2.line(img, (sx, y1 + 48), (dx, y1 + 48), BORDO, 1)
        if not self.eventi.recenti:
            testi.append((sx, y1 + 73, "Nessun evento registrato", F["testo"], TESTO_DIM, "lm"))
            return

        for i, e in enumerate(reversed(self.eventi.recenti)):
            tempo, _, evento = e.partition("  ")
            mano, _, descrizione = evento.partition(" · ")
            y = y1 + 50 + i * 55
            colore = AMBRA if "braccio teso" in descrizione else ACCENTO
            cv2.circle(img, (sx + 3, y + 13), 3, colore, -1, cv2.LINE_AA)
            testi.append((sx + 14, y + 13, tempo, F["mono"], TESTO_SEC, "lm"))
            testi.append((dx, y + 13, mano, F["piccolo"], TESTO_SEC, "rm"))
            descrizione = descrizione[:1].upper() + descrizione[1:]
            for j, riga in enumerate(due_righe(descrizione, F["testo"], dx - sx)):
                testi.append((sx, y + 31 + j * 15, riga, F["testo"], TESTO, "lm"))
            if i + 1 < len(self.eventi.recenti):
                cv2.line(img, (sx, y + 55), (dx, y + 55), BORDO, 1)

    def _render_riproduzione(self):
        img = np.full((ALTEZZA_UI, LARGHEZZA_UI, 3), SFONDO, dtype=np.uint8)
        self.ui["pulsanti"] = []
        testi = []
        self._testata(img, testi, riproduzione=True)
        scheda(img, PANNELLO_VIDEO)
        x1, y1, x2, y2 = VANO_VIDEO
        img[y1:y2, x1:x2] = FONDO_VIDEO
        h, w = self.scena["base"].shape[:2]
        k = min((x2 - x1) / w, (y2 - y1) / h)
        larg, alt = max(1, round(w * k)), max(1, round(h * k))
        x, y = x1 + (x2 - x1 - larg) // 2, y1 + (y2 - y1 - alt) // 2
        self.ui["vista"] = (x, y, x + larg, y + alt)
        bersagli = self.calibra["tmp"] if self.calibra is not None else self.bersagli
        img[y:y + alt, x:x + larg] = self._fotogramma_annotato(larg, alt, bersagli)
        cv2.line(img, (x1, y1 - 1), (x2 - 1, y1 - 1), BORDO, 1)
        cv2.line(img, (x1, y2), (x2 - 1, y2), BORDO, 1)

        self._disegna_sorgente(img, testi)
        self._disegna_controlli(img, testi)
        self._disegna_rilevamento(img, testi)
        self._disegna_eventi(img, testi)
        return disegna_testi(img, testi)

    def _disegna_schema(self, img, testi):
        x1, y1, x2, y2 = 555, 118, 1104, 554
        sx, dx = x1 + 18, x2 - 18
        scheda(img, (x1, y1, x2, y2))
        testi.append((sx, y1 + 25, "Schema del gesto", self.F["titolo"], TESTO, "lm"))
        alto, basso = y1 + 50, y2 - 46
        cv2.rectangle(img, (x1 + 1, alto), (x2 - 1, basso), FONDO_VIDEO, -1)
        for x in range(x1 + 27, x2 - 1, 27):
            cv2.line(img, (x, alto), (x, basso), GRIGLIA, 1)
        for y in range(alto + 27, basso, 27):
            cv2.line(img, (x1 + 1, y), (x2 - 1, y), GRIGLIA, 1)
        for y in (alto, basso):
            cv2.line(img, (x1 + 1, y), (x2 - 1, y), BORDO, 1)

        sp_sx, sp_dx = (x1 + 112, y1 + 222), (x1 + 188, y1 + 195)
        anca_sx, anca_dx = (x1 + 134, y1 + 339), (x1 + 207, y1 + 313)
        gomito_sx, polso_sx = (x1 + 95, y1 + 271), (x1 + 116, y1 + 312)
        corpo = [(sp_sx, sp_dx), (sp_sx, anca_sx), (sp_dx, anca_dx),
                 (anca_sx, anca_dx), (sp_sx, gomito_sx), (gomito_sx, polso_sx)]
        disegna_corpo(img, corpo, (1, 1))

        gomito, polso = (x1 + 252, y1 + 176), (x1 + 309, y1 + 150)
        disegna_arto(img, sp_dx, gomito, polso, ACCENTO)
        profilo = [(309, 150), (320, 139), (362, 122), (366, 127),
                   (338, 140), (336, 154), (326, 160), (310, 156)]
        mano = np.array([(x1 + x, y1 + y) for x, y in profilo], dtype=np.int32)
        cv2.fillPoly(img, [mano], FONDO_ACCENTO, cv2.LINE_AA)
        cv2.polylines(img, [mano], True, ACCENTO, 1, cv2.LINE_AA)
        punta = (x1 + 366, y1 + 125)
        disegna_raggio(img, polso, punta, ACCENTO, freccia=39, massimo=83)
        bersaglio = (x1 + 456, y1 + 86)
        cv2.circle(img, bersaglio, 25, FONDO_ACCENTO, 1, cv2.LINE_AA)
        cv2.circle(img, bersaglio, 16, ACCENTO, 1, cv2.LINE_AA)
        cv2.circle(img, bersaglio, 3, ACCENTO, -1, cv2.LINE_AA)

        for x, testo, colore in ((sx, "Pointing", ACCENTO), (sx + 113, "Braccio teso", AMBRA)):
            cv2.circle(img, (x + 3, y2 - 22), 3, colore, -1, cv2.LINE_AA)
            testi.append((x + 15, y2 - 22, testo, self.F["piccolo"], TESTO_SEC, "lm"))

    def _render_home(self):
        img = np.full((ALTEZZA_UI, LARGHEZZA_UI, 3), SFONDO, dtype=np.uint8)
        self.ui["pulsanti"] = []
        self.ui["barra"] = None
        self.ui["vista"] = None
        F = self.F
        testi = []
        self._testata(img, testi, riproduzione=False)
        sx, dx = 56, 481
        testi += [(sx, 159, "Rilevatore di", F["h1"], TESTO, "lt"),
                  (sx, 222, "pointing", F["h1"], TESTO, "lt"),
                  (sx, 309, "Scegli la sorgente da analizzare.", F["sottotitolo"], TESTO_SEC, "lm")]
        self._pulsante(img, testi, "apri_video", (sx, 341, dx, 395),
                       "Apri video", "video", primario=True, tasto="O")
        self._pulsante(img, testi, "webcam", (sx, 407, dx, 461),
                       "Usa la webcam", "webcam", tasto="W")
        self._disegna_schema(img, testi)

        messaggio = self._msg_attivo()
        if messaggio:
            self._notifica(img, testi, (sx, 484, dx, 536), messaggio)

        cv2.line(img, (sx, 610), (LARGHEZZA_UI - sx, 610), BORDO, 1)
        x, y = sx, 646
        for tasti, azione in ((("Spazio",), "Pausa"), (("A", "D"), "Passo per frame"),
                              (("T",), "Tracciamento"), (("P",), "Poster"), (("Q",), "Esci")):
            for t in tasti:
                x += self._tasto(img, testi, x, y, t) + 6
            testi.append((x + 2, y, azione, F["piccolo"], TESTO_SEC, "lm"))
            x += math.ceil(F["piccolo"].getlength(azione)) + 30
        return disegna_testi(img, testi)
