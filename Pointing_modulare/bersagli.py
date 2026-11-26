"""Assegnazione dei bersagli e salvataggio della calibrazione."""

import json
import math
import os
from configurazione import (
    BERSAGLIO_CAMERA,
    POSTER,
)


def assegna_bersagli(record, bersagli_px, solo_poster, tolleranza):
    """Collega ogni mano/braccio al poster indicato e usa i poster per correggere il gesto.
    bersagli_px: {nome: (x, y)} in pixel del frame (vuoto se i poster non sono stati segnati).
    - r['bersaglio']: poster verso cui punta il braccio (angolo spalla->punta contro
      spalla->poster entro 'tolleranza' gradi), oppure BERSAGLIO_CAMERA, oppure None.
    - 'Altro' con braccio teso diretto a un poster diventa 'Braccio teso'.
    - Con i poster segnati, un 'Braccio teso' che non punta a nulla diventa 'Altro'
      (e con solo_poster anche un 'Pointing' fuori bersaglio)."""
    for r in record:
        b = None
        if r.get("verso_camera"):
            b = BERSAGLIO_CAMERA
        elif bersagli_px:
            origine = r.get("spalla") or r["base"]
            rx, ry = r["punta"][0] - origine[0], r["punta"][1] - origine[1]
            nr = math.hypot(rx, ry)
            if nr >= 15:
                migliore = None
                for nome, (tx, ty) in bersagli_px.items():
                    vx, vy = tx - origine[0], ty - origine[1]
                    nv = math.hypot(vx, vy)
                    if nv < 1:
                        continue
                    c = (rx * vx + ry * vy) / (nr * nv)
                    a = math.degrees(math.acos(max(-1.0, min(1.0, c))))
                    if a <= tolleranza and (migliore is None or a < migliore[0]):
                        migliore = (a, nome)
                if migliore:
                    b = migliore[1]
        r["bersaglio"] = b
        if r["gesto"] == "Altro" and r.get("braccio") and b:
            r["gesto"] = "Braccio teso"
        elif bersagli_px and b is None:
            if r["gesto"] == "Braccio teso" or (solo_poster and r["gesto"] == "Pointing"):
                r["gesto"] = "Altro"

# ------------------------- Poster segnati a mano --------------------------
def percorso_poster(sorg):
    if sorg.get("percorso"):
        return os.path.splitext(sorg["percorso"])[0] + "_poster.json"
    return "poster_webcam.json"


def carica_poster(percorso):
    """{nome: (x, y)} con coordinate normalizzate (0-1) sull'immagine; {} se non c'e' il file."""
    try:
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
        return {n: (float(dati[n][0]), float(dati[n][1])) for n in POSTER if n in dati}
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return {}


def salva_poster(percorso, bersagli):
    try:
        with open(percorso, "w", encoding="utf-8") as f:
            json.dump({n: list(p) for n, p in bersagli.items()}, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False
