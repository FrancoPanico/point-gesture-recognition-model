"""Funzioni grafiche per scheletro, frecce, elementi UI e testo."""

from PIL import Image
from PIL import ImageDraw
import cv2
import math
import numpy as np
from configurazione import (
    DIREZIONI,
    INDICE_TIP,
)
from rilevamento import (
    mp_hands,
)
from stile import (
    BORDO,
    OMBRA,
    PANNELLO,
    TESTO_DIM,
    TESTO_SEC,
    TRACCIAMENTO,
)


# ------------------------------ Disegno base ------------------------------
def schiarisci(colore, d=22):
    return tuple(min(255, v + d) for v in colore)


def tronca(testo, font, larghezza_max):
    if font.getlength(testo) <= larghezza_max:
        return testo
    if font.getlength("…") > larghezza_max:
        return ""
    while testo and font.getlength(testo + "…") > larghezza_max:
        testo = testo[:-1]
    return testo + "…"


def due_righe(testo, font, larghezza):
    if font.getlength(testo) <= larghezza:
        return (testo,)
    parole = testo.split()
    riga = parole.pop(0)
    while parole and font.getlength(riga + " " + parole[0]) <= larghezza:
        riga += " " + parole.pop(0)
    return (tronca(riga, font, larghezza), tronca(" ".join(parole), font, larghezza))


def rett_arrotondato(img, p1, p2, colore, r):
    x1, y1 = p1
    x2, y2 = p2
    r = max(0, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
    cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), colore, -1)
    cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), colore, -1)
    for cx, cy in ((x1 + r, y1 + r), (x2 - r, y1 + r), (x1 + r, y2 - r), (x2 - r, y2 - r)):
        cv2.circle(img, (cx, cy), r, colore, -1, cv2.LINE_AA)


def scheda(img, rett, sfondo=PANNELLO, bordo=BORDO, raggio=12):
    x1, y1, x2, y2 = rett
    rett_arrotondato(img, (x1, y1), (x2, y2), bordo, raggio)
    rett_arrotondato(img, (x1 + 1, y1 + 1), (x2 - 1, y2 - 1), sfondo, raggio - 1)


def in_rettangolo(x, y, rett):
    x1, y1, x2, y2 = rett
    return x1 <= x < x2 and y1 <= y < y2


def disegna_testi(img, testi):
    if not testi:
        return img
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    pennello = ImageDraw.Draw(pil)
    for x, y, t, font, c, ancora in testi:
        pennello.text((x, y), t, font=font, fill=c[::-1], anchor=ancora)
    img[:] = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
    return img


def disegna_icona(img, nome, x, y, colore):
    """Icone tracciate in una griglia di 16 pixel."""
    def linea(a, b):
        cv2.line(img, (x + a[0], y + a[1]), (x + b[0], y + b[1]), colore, 1, cv2.LINE_AA)

    if nome == "video":
        cv2.rectangle(img, (x - 7, y - 6), (x + 7, y + 6), colore, 1, cv2.LINE_AA)
        for dy in (-3, 2):
            linea((-7, dy), (-4, dy))
            linea((4, dy), (7, dy))
    elif nome == "webcam":
        cv2.rectangle(img, (x - 7, y - 6), (x + 7, y + 4), colore, 1, cv2.LINE_AA)
        cv2.circle(img, (x, y - 1), 3, colore, 1, cv2.LINE_AA)
        linea((-4, 7), (4, 7))
    elif nome == "pausa":
        linea((-3, -6), (-3, 6))
        linea((3, -6), (3, 6))
    elif nome == "riprendi":
        punti = np.array([(x - 4, y - 6), (x + 6, y), (x - 4, y + 6)], dtype=np.int32)
        cv2.fillConvexPoly(img, punti, colore, cv2.LINE_AA)
    elif nome in ("prima", "dopo"):
        verso = -1 if nome == "prima" else 1
        linea((5 * verso, -6), (5 * verso, 6))
        linea((-4 * verso, -4), (1 * verso, 0))
        linea((1 * verso, 0), (-4 * verso, 4))
    elif nome == "traccia":
        punti = ((-5, 4), (0, -4), (6, -1))
        linea(punti[0], punti[1])
        linea(punti[1], punti[2])
        for dx, dy in punti:
            cv2.circle(img, (x + dx, y + dy), 2, colore, -1, cv2.LINE_AA)
    elif nome == "poster":
        cv2.circle(img, (x, y), 6, colore, 1, cv2.LINE_AA)
        cv2.circle(img, (x, y), 2, colore, -1, cv2.LINE_AA)
    elif nome == "esci":
        linea((-4, -4), (4, 4))
        linea((-4, 4), (4, -4))
    elif nome == "info":
        cv2.circle(img, (x, y), 7, colore, 1, cv2.LINE_AA)
        cv2.circle(img, (x, y - 3), 1, colore, -1, cv2.LINE_AA)
        linea((0, 0), (0, 4))


def scala_punto(p, scala):
    return (round(p[0] * scala[0]), round(p[1] * scala[1]))


def etichetta_frame(img, testi, x, y, testo, font, colore):
    """Etichetta compatta mantenuta all'interno del fotogramma."""
    h, w = img.shape[:2]
    alt = getattr(font, "size", 12) + 8
    if w < 42 or h < alt + 6:
        return
    testo = tronca(testo, font, w - 24)
    larg = math.ceil(font.getlength(testo)) + 14
    x = max(4, min(x, w - larg - 4))
    y = max(3, min(y, h - alt - 3))
    rett_arrotondato(img, (x, y), (x + larg, y + alt), OMBRA, 5)
    testi.append((x + 7, y + alt // 2, testo, font, colore, "lm"))


def disegna_scheletro(img, pts, colore, sottile=False):
    ombra, linea, r_giunto = (3, 1, 2) if sottile else (4, 2, 2)
    for a, b in mp_hands.HAND_CONNECTIONS:
        cv2.line(img, pts[a], pts[b], OMBRA, ombra, cv2.LINE_AA)
    for a, b in mp_hands.HAND_CONNECTIONS:
        cv2.line(img, pts[a], pts[b], colore, linea, cv2.LINE_AA)
    for i, p in enumerate(pts):
        r = r_giunto + (2 if i == INDICE_TIP and not sottile else 0)
        cv2.circle(img, p, r + 1, OMBRA, -1, cv2.LINE_AA)
        cv2.circle(img, p, r, colore, -1, cv2.LINE_AA)


def disegna_arto(img, sp, go, po, colore, sottile=False):
    ombra, linea = (4, 1) if sottile else (5, 2)
    for a, b in ((sp, go), (go, po)):
        cv2.line(img, a, b, OMBRA, ombra, cv2.LINE_AA)
    for a, b in ((sp, go), (go, po)):
        cv2.line(img, a, b, colore, linea, cv2.LINE_AA)
    for p in (sp, go, po):
        cv2.circle(img, p, 4, OMBRA, -1, cv2.LINE_AA)
        cv2.circle(img, p, 3, colore, -1, cv2.LINE_AA)


def disegna_corpo(img, segmenti, scala):
    """Scheletro del corpo senza testa (busto, braccia, gambe), sottile e discreto."""
    visti = set()
    for a, b in segmenti:
        p1, p2 = scala_punto(a, scala), scala_punto(b, scala)
        cv2.line(img, p1, p2, OMBRA, 3, cv2.LINE_AA)
        cv2.line(img, p1, p2, TRACCIAMENTO, 1, cv2.LINE_AA)
        visti.update((p1, p2))
    for p in visti:
        cv2.circle(img, p, 3, OMBRA, -1, cv2.LINE_AA)
        cv2.circle(img, p, 2, TESTO_SEC, -1, cv2.LINE_AA)


def riquadro(pts, w, h, margine=15):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (max(3, min(xs) - margine), max(3, min(ys) - margine),
            min(w - 4, max(xs) + margine), min(h - 4, max(ys) + margine))


def disegna_angoli(img, box, colore):
    x1, y1, x2, y2 = box
    lunghezza = min(12, (x2 - x1) // 3, (y2 - y1) // 3)
    if lunghezza < 3:
        return
    for (cx, cy, sx, sy) in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
        for spessore, c in ((3, OMBRA), (1, colore)):
            cv2.line(img, (cx, cy), (cx + sx * lunghezza, cy), c, spessore, cv2.LINE_AA)
            cv2.line(img, (cx, cy), (cx, cy + sy * lunghezza), c, spessore, cv2.LINE_AA)


def disegna_raggio(img, base, punta, colore, freccia=60, massimo=380):
    """Freccia piena all'inizio, poi linea tratteggiata che prosegue nella direzione indicata."""
    dx, dy = punta[0] - base[0], punta[1] - base[1]
    n = math.hypot(dx, dy)
    if n < 1:
        return
    ux, uy = dx / n, dy / n
    h, w = img.shape[:2]
    fine = (int(punta[0] + ux * freccia), int(punta[1] + uy * freccia))
    cv2.arrowedLine(img, punta, fine, OMBRA, 5, cv2.LINE_AA, 0, 0.18)
    cv2.arrowedLine(img, punta, fine, colore, 2, cv2.LINE_AA, 0, 0.18)
    d = freccia + 12
    while d < massimo:
        p1 = (int(punta[0] + ux * d), int(punta[1] + uy * d))
        p2 = (int(punta[0] + ux * (d + 8)), int(punta[1] + uy * (d + 8)))
        if not (0 <= p1[0] < w and 0 <= p1[1] < h):
            break
        cv2.line(img, p1, p2, colore, 1, cv2.LINE_AA)
        d += 18


def disegna_bussola(img, centro, raggio, direz, colore):
    cx, cy = centro
    cv2.circle(img, centro, raggio + 5, BORDO, 1, cv2.LINE_AA)
    for k in range(8):
        a = math.radians(k * 45)
        p = (round(cx + raggio * math.cos(a)), round(cy - raggio * math.sin(a)))
        if direz == DIREZIONI[k]:
            cv2.arrowedLine(img, centro, p, colore, 2, cv2.LINE_AA, 0, 0.34)
        else:
            cv2.circle(img, p, 1, TESTO_DIM, -1, cv2.LINE_AA)
    cv2.circle(img, centro, 2, colore, -1, cv2.LINE_AA)
