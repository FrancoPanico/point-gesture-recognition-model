"""Calcoli geometrici sui landmark di mano e corpo."""

import math
import numpy as np
from configurazione import (
    ANULARE_PIP,
    ANULARE_TIP,
    DIREZIONI,
    INDICE_PIP,
    INDICE_TIP,
    MEDIO_PIP,
    MEDIO_TIP,
    MIGNOLO_PIP,
    MIGNOLO_TIP,
    POLSO,
    SEGMENTI_CORPO,
    VISIBILITA_MIN,
)


# ------------------------------- Geometria --------------------------------
def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y) 
    # Questa funzione calcola la distanza euclidea bidimensionale tra due punti.
    # sqrt((x2 - x1)^2 + (y2 - y1)^2) è equivalente a math.hypot(x2 - x1, y2 - y1)

def dito_esteso(lm, tip, pip):
    return dist(lm[POLSO], lm[tip]) > dist(lm[POLSO], lm[pip])
    # lm = lista di landmark della mano
    # tip = indice del landmark della punta del dito
    # pip = indice del landmark della falange prossimale del dito

    # il codice confronta la distanza tra il polso e la punta del dito con la distanza tra il polso e la falange prossimale del dito.
    # Se la distanza dal polso alla punta del dito è maggiore della distanza dal polso alla falange prossimale, allora il dito è considerato esteso (cioè non piegato). 
    # In altre parole, se la punta del dito è più lontana dal polso rispetto alla falange prossimale, il dito è esteso.

    # Limite dell'implementazione: questo metodo utilizza un criterio geometrico semplificato. 
    # Un dito parzialmente piegato potrebbe risultare comunque esteso. 
    # Inoltre, la prospettiva della telecamera influenza le distanze osservate.

def dita_estese(lm):
    """(indice esteso?, almeno un'altra dita estesa tra medio/anulare/mignolo?)"""
    indice = dito_esteso(lm, INDICE_TIP, INDICE_PIP)
    altre = (dito_esteso(lm, MEDIO_TIP, MEDIO_PIP)
             or dito_esteso(lm, ANULARE_TIP, ANULARE_PIP)
             or dito_esteso(lm, MIGNOLO_TIP, MIGNOLO_PIP))
    return indice, altre

    # Questa funzione richiama quattro volte la funzione precedente, al massimo, per valutare la configurazione complessiva della mano.
    # Restituisce una tupla di due valori booleani:
    # - Il primo valore indica se l'indice è esteso.
    # - Il secondo valore indica se almeno uno degli altri tre dita (medio, anulare, mignolo) è esteso.

    # La configurazione della mano che cerchiamo per il pointing è:
    # indice = True e altre = False


    # in rilevamento.py utilizzeremo: 
    # if indice and not altre and staccato:
    #     gesto = "Pointing"


def direzione(dx, dy):
    angolo = math.degrees(math.atan2(-dy, dx)) % 360
    # Questa funzione calcola la direzione di un vettore bidimensionale (dx, dy) in termini di una delle otto direzioni cardinali (N, NE, E, SE, S, SW, W, NW).
    # La funzione utilizza la funzione atan2 per calcolare l'angolo del vettore rispetto all'asse x positivo, quindi converte l'angolo in gradi e lo normalizza nell'intervallo [0, 360).

# Infine, l'angolo viene mappato a una delle otto direzioni cardinali utilizzando un intervallo di 45 gradi per ciascuna direzione.

    return DIREZIONI[int(((angolo + 22.5) % 360) // 45)]
    # + 22.5 centra ciascun settore sulla direzione desiderata.
    # % 360 gestisce il passaggio tra 360° e 0°.
    # // 45 esegue la divisione intera.
    # int() converte il risultato in un indice intero.





def angolo_gomito(sp, go, po):

    # sp	Spalla
    # go	Gomito
    # po	Polso

    # Costruiamo due vettori con origine comune nel gomito. 
    # In questo modo possiamo calcolare l'angolo interno del gomito.
    v1 = (sp[0] - go[0], sp[1] - go[1])
    v2 = (po[0] - go[0], po[1] - go[1])

    # Calcoliamo la lunghezza dei due vettori. 
    # L'asterisco * serve a estrarre gli elementi della tupla. ES: v1 = (3, 4) allora math.hypot(*v1) = math.hypot(3, 4) = 5.0
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 < 1e-6 or n2 < 1e-6:  # 1e-6 = 0.000001. Se uno dei vettori ha lunghezza praticamente nulla, interrompiamo la funzione. 
                                # Questo evita una divisione per zero nel calcolo successivo.
        return 0.0

    # Prodotto scalare tra i due vettori, normalizzato per le loro lunghezze.
    c = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    # L'arcocoseno permette di ricavare l'angolo partendo dal coseno.
    # max(-1.0, min(1.0, c)) --> Serve a mantenere c nell'intervallo matematicamente valido per l'arcocoseno, ovvero [-1,1].
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def braccio_dritto(sp, go, po):
    """Braccio quasi dritto (gomito poco piegato)."""
    return angolo_gomito(sp, go, po) >= 145


def corpo_visibile(pl):
    """True se le spalle sono visibili: serve almeno il busto per valutare lo stacco."""
    return pl is not None and min(
        pl[11].visibility, # spalla sinistra
        pl[12].visibility # spalla destra
        ) >= VISIBILITA_MIN
# pl = lista dei 33 landmark restituiti da MediaPipe Pose.
# .visibility è il punteggio di visibilità stimato da MediaPipe.




###### CONTROLLARE: 
def geometria_busto(pl, W, H):
    """(centro spalle, versore 'giu' del busto, lunghezza busto) in pixel, 2D.
    Asse dal centro spalle al centro anche; se le anche non si vedono (o il risultato e'
    assurdo) il busto e' stimato dalle spalle, in verticale."""


# Vogliamo ricavare tre informazioni:
# - Il punto centrale tra le spalle.
# - La direzione del busto, dalle spalle alle anche.
# - La lunghezza del busto nell'immagine.

# W (Width) = larghezza del fotogramma in pixel.
# H (Height) = altezza del fotogramma in pixel.
# Nel file rilevamento.py trovi infatti: H, W = frame.shape[:2]

# MediaPipe restituisce le coordinate dei landmark normalizzate rispetto alle dimensioni del fotogramma.
    # es. pl[11].x = 0.75, pl[11].y = 0.50. 
    # La sua posizione in pixel sarà:x = 0.75 * 1920  # 1440 pixel
    # y = 0.50 * 1080  # 540 pixel
    # ABBIAMO QUINDI LOCALIZZATO ENTRAMBE LE SPALLE NELL'IMMAGINE.






    sx = np.array([pl[11].x * W, pl[11].y * H])
    dx = np.array([pl[12].x * W, pl[12].y * H])
    centro = (sx + dx) / 2 # Centro delle spalle, in pixel.
    larg = max(float(np.linalg.norm(sx - dx)), 1.0) # larghezza delle spalle, in pixel. Se le spalle coincidono (caso improbabile), larg = 1.0 per evitare divisioni per zero.
    asse = None
    if min(pl[23].visibility, pl[24].visibility) >= VISIBILITA_MIN:
        anche = np.array([(pl[23].x + pl[24].x) / 2 * W, (pl[23].y + pl[24].y) / 2 * H])
        asse = anche - centro
        if np.linalg.norm(asse) < 0.5 * larg:
            asse = None
    if asse is None:
        asse = np.array([0.0, 1.5 * larg])
    lung = float(np.linalg.norm(asse)) # lunghezza del busto, in pixel.
    return centro, asse / lung, lung # restituiamo: il centro delle spalle, il versore della direzione del busto e la lunghezza del busto, tutti in pixel.


def stacco_braccio(pl, W, H, i_spalla, polso_xy):
# ingresso:
# 1- pl = lista dei landmark del corpo restituiti da MediaPipe Pose.
# 2- W = larghezza del fotogramma in pixel.
# 3- H = altezza del fotogramma in pixel.   
# 4- i_spalla = indice del landmark della spalla (11 per la sinistra, 12 per la destra).
# 5- polso_xy = coordinate del polso in pixel, calcolate da la funzione polso_2D() in rilevamento.py.


    """Angolo in gradi tra il braccio (spalla -> polso) e la direzione 'giu'' del busto.
    Calcolato in 2D sull'immagine: la profondita' z di MediaPipe e' troppo rumorosa e
    dava falsi pointing con le braccia lungo i fianchi.
      braccio lungo il fianco ~ 0-25 gradi, orizzontale ~ 90, mano sopra la spalla > 90.
    Il braccio e' 'staccato' se l'angolo e' >= STACCO_ANGOLO_MIN."""
    _, giu, _ = geometria_busto(pl, W, H) # qui recuperiamo il versore della direzione "giu'" del busto, in pixel, per calcolare l'angolo che forma con il vettore spalla-polso.
    # recuperiamo, quindi, la direzione del busto.
    spalla = np.array([pl[i_spalla].x * W, pl[i_spalla].y * H])
    v = np.asarray(polso_xy[:2], dtype=float) - spalla # calcoliamo il vettore spalla-polso, in pixel.
    nv = float(np.linalg.norm(v)) # calcoliamo la lunghezza del vettore spalla-polso, in pixel.
    if nv < 1e-6:
        return 0.0 # verifico che il vettore spalla-polso non sia praticamente nullo, altrimenti ritorno 0.0 per evitare divisioni per zero.
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(v, giu)) / nv)))) # calcolo angolo braccio-busto.


def verso_camera(pl, W, H, i_spalla, i_gomito, i_polso, polso_xy):
    """Il braccio punta verso la telecamera? In 2D il braccio appare accorciato (polso vicino
    alla spalla rispetto alla lunghezza spalla-gomito-polso) e il polso e' piu' vicino alla
    camera della spalla (z di MediaPipe). Servono entrambi i segnali, perche' la z da sola e'
    rumorosa."""
    if min(pl[i].visibility for i in (i_spalla, i_gomito, i_polso)) < VISIBILITA_MIN:
        return False
    sp = np.array([pl[i_spalla].x * W, pl[i_spalla].y * H])
    go = np.array([pl[i_gomito].x * W, pl[i_gomito].y * H])
    u = float(np.linalg.norm(sp - go))
    f = float(np.linalg.norm(go - np.array([pl[i_polso].x * W, pl[i_polso].y * H])))
    if u + f < 1:
        return False
    reach = float(np.linalg.norm(np.asarray(polso_xy[:2], dtype=float) - sp))
    if reach / (u + f) > 0.7:
        return False
    _, _, lung = geometria_busto(pl, W, H)
    return (pl[i_spalla].z - pl[i_polso].z) * W > 0.25 * lung


def estrai_corpo(pl, W, H):
    """Segmenti del corpo (testa esclusa) con entrambi gli estremi visibili, in pixel."""
    segmenti = []
    for a, b in SEGMENTI_CORPO:
        if min(pl[a].visibility, pl[b].visibility) >= VISIBILITA_MIN:
            segmenti.append(((pl[a].x * W, pl[a].y * H), (pl[b].x * W, pl[b].y * H)))
    return segmenti
