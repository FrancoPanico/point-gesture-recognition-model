"""Gestione temporale, registro CSV e riepilogo degli eventi."""

from collections import deque
from datetime import datetime
import csv
from configurazione import (
    GESTI_ATTIVI,
    MIN_DURATA_RIEPILOGO,
)


# ------------------------- Tempo, eventi, CSV -----------------------------
def fmt_video(t):
    m = int(t // 60)
    return f"{m:02d}:{t - 60 * m:04.1f}"


def fmt_breve(t):
    return f"{int(t) // 60:02d}:{int(t) % 60:02d}"


def fmt_orologio(t):
    return datetime.fromtimestamp(t).strftime("%H:%M:%S")


class Eventi:
    def __init__(self, nome_csv, fmt):
        self.fmt = fmt
        self.recenti = deque(maxlen=5)
        self.segmenti = []   # (gesto, mano, t_inizio, t_fine, direzione, bersaglio)
        self.file = None
        self.writer = None
        if nome_csv:
            self.file = open(nome_csv, "w", newline="", encoding="utf-8")
            self.writer = csv.writer(self.file)
            self.writer.writerow(["tempo", "mano", "evento", "gesto", "durata_s",
                                  "direzione", "braccio_teso", "bersaglio"])
            print(f"Registro CSV: {nome_csv}")

    def _scrivi(self, *riga):
        if self.writer:
            self.writer.writerow(riga)
            self.file.flush()

    def cambia(self, mano, stato, nuovo, t, direz="", braccio=False, bersaglio=""):
        """Chiude l'evento precedente e apre quello nuovo (nuovo=None: solo chiusura)."""
        ts = self.fmt(t)
        if stato["gesto"] is not None:
            durata = t - stato["inizio"]
            b_old = stato.get("bersaglio", "")
            nome_old = stato["gesto"] + (f" verso {b_old}" if b_old else "")
            print(f"[{ts}] Mano {mano}: fine {nome_old} ({durata:.1f} s)")
            self._scrivi(ts, mano, "fine", stato["gesto"], f"{durata:.2f}", "", "", b_old)
            self.recenti.append(f"{ts}  {mano} · fine {nome_old.lower()} ({durata:.1f} s)")
            self.segmenti.append((stato["gesto"], mano, stato["inizio"], t,
                                  stato.get("direz", ""), b_old))
        if nuovo is not None:
            if bersaglio:
                extra = f" verso {bersaglio} ({direz})" if direz else f" verso {bersaglio}"
            else:
                extra = f" verso {direz}" if direz else ""
            print(f"[{ts}] Mano {mano}: inizio {nuovo}{extra}")
            self._scrivi(ts, mano, "inizio", nuovo, "", direz, "si" if braccio else "no", bersaglio)
            self.recenti.append(f"{ts}  {mano} · {nuovo.lower()}{extra}")
        stato["gesto"] = nuovo
        stato["inizio"] = t
        stato["direz"] = direz
        stato["bersaglio"] = bersaglio

    def riepilogo(self):
        print("\n=== Riepilogo ===")
        for gesto, titolo in (("Pointing", "Pointing"),
                              ("Braccio teso", "Braccio teso (probabile pointing, mano non riconosciuta)")):
            validi = [s for s in self.segmenti if s[0] == gesto and s[3] - s[2] >= MIN_DURATA_RIEPILOGO]
            if not validi:
                if gesto == "Pointing":
                    print("Pointing: nessuno rilevato.")
                continue
            print(f"{titolo}:")
            for _, mano, t0, t1, direz, bers in validi:
                extra = f" verso {bers}" if bers else (f" verso {direz}" if direz else "")
                print(f"  Mano {mano}: {self.fmt(t0)} -> {self.fmt(t1)}  ({t1 - t0:.1f} s){extra}")
            print(f"  Totale: {len(validi)} eventi, {sum(s[3] - s[2] for s in validi):.1f} s")
        per_bers = {}
        for gesto, _, t0, t1, _, bers in self.segmenti:
            if gesto in GESTI_ATTIVI and bers and t1 - t0 >= MIN_DURATA_RIEPILOGO:
                n, d = per_bers.get(bers, (0, 0.0))
                per_bers[bers] = (n + 1, d + t1 - t0)
        if per_bers:
            print("Per poster:")
            for bers, (n, d) in sorted(per_bers.items()):
                print(f"  {bers}: {n} eventi, {d:.1f} s")

    def chiudi(self):
        if self.file:
            self.file.close()
            self.file = None
            self.writer = None
