"""MediaPipe: ricerca della mano e classificazione dei gesti."""

from collections import namedtuple
import cv2
import math
import mediapipe as mp
from configurazione import (
    BRACCIA,
    INDICE_MCP,
    INDICE_TIP,
    POLSO,
    ROI_FATTORE,
    STACCO_ANGOLO_MIN,
    VISIBILITA_MIN,
)
from geometria import (
    braccio_dritto,
    corpo_visibile,
    dita_estese,
    estrai_corpo,
    geometria_busto,
    stacco_braccio,
    verso_camera,
)


mp_hands = mp.solutions.hands
mp_pose = mp.solutions.pose

Punto = namedtuple("Punto", "x y")

# ------------------------------ Rilevamento -------------------------------
def mano_da_ritaglio(hands_rit, rgb, centro, lato, polso_pose):
    """Cerca la mano in un ritaglio ingrandito attorno al polso.
    Restituisce 21 Punto in coordinate del frame intero, oppure None."""
    H, W = rgb.shape[:2]
    lato = int(min(lato, W, H))
    x0 = int(max(0, min(centro[0] - lato / 2, W - lato)))
    y0 = int(max(0, min(centro[1] - lato / 2, H - lato)))
    ritaglio = rgb[y0:y0 + lato, x0:x0 + lato]
    inter = cv2.INTER_CUBIC if lato < 384 else cv2.INTER_AREA
    ritaglio = cv2.resize(ritaglio, (384, 384), interpolation=inter)

    ris = hands_rit.process(ritaglio)
    if not ris.multi_hand_landmarks:
        return None
    pts = [Punto(x0 + p.x * lato, y0 + p.y * lato) for p in ris.multi_hand_landmarks[0].landmark]
    if math.hypot(pts[0].x - polso_pose[0], pts[0].y - polso_pose[1]) > 0.3 * lato:
        return None
    return pts


def mani_da_roi(hands_roi, rgb, centro, lato):
    """Cerca fino a 2 mani in una zona quadrata ingrandita (es. attorno a tutta la persona).
    Restituisce una lista di mani, ognuna di 21 Punto in coordinate del frame intero."""
    H, W = rgb.shape[:2]
    lato = int(max(160, min(lato, W, H)))
    x0 = int(max(0, min(centro[0] - lato / 2, W - lato)))
    y0 = int(max(0, min(centro[1] - lato / 2, H - lato)))
    ritaglio = rgb[y0:y0 + lato, x0:x0 + lato]
    dim = 640
    inter = cv2.INTER_CUBIC if lato < dim else cv2.INTER_AREA
    ritaglio = cv2.resize(ritaglio, (dim, dim), interpolation=inter)
    ris = hands_roi.process(ritaglio)
    if not ris.multi_hand_landmarks:
        return []
    return [[Punto(x0 + p.x * lato, y0 + p.y * lato) for p in mano.landmark]
            for mano in ris.multi_hand_landmarks]


def analizza(frame, pose, hands_rit, hands_pieno, hands_roi, specchio):
    """Restituisce (record, corpo).
    record: uno per lato (Sinistra/Destra). gesto: 'Pointing', 'Braccio teso' oppure 'Altro'
            (mano vista ma non in pointing, oppure braccio non staccato dal corpo).
    corpo: segmenti del corpo (testa esclusa) in pixel, lista vuota se il corpo non si vede.
    Pointing e Braccio teso valgono solo se il braccio e' staccato dal corpo."""
    H, W = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    record = []
    corpo = []
    pl = None   # landmark della posa, se il corpo e' stato trovato

    def nome_visto(anat):
        # In un'immagine specchiata destra e sinistra si scambiano
        if specchio:
            return "Destra" if anat == "Sinistra" else "Sinistra"
        return anat

    if pose is not None:
        ris_pose = pose.process(rgb)
        if ris_pose.pose_landmarks and corpo_visibile(ris_pose.pose_landmarks.landmark):
            pl = ris_pose.pose_landmarks.landmark
            corpo = estrai_corpo(pl, W, H)

            # Strada 1: per ogni braccio visibile, ritaglio ingrandito attorno al polso
            for nome_anat, (i_s, i_g, i_p) in BRACCIA.items():
                if min(pl[i].visibility for i in (i_s, i_g, i_p)) < VISIBILITA_MIN:
                    continue
                sp = (pl[i_s].x * W, pl[i_s].y * H)
                go = (pl[i_g].x * W, pl[i_g].y * H)
                po = (pl[i_p].x * W, pl[i_p].y * H)

                angolo = stacco_braccio(pl, W, H, i_s, po)
                # mano verso la camera: braccio accorciato in 2D ma in avanti in profondita'
                vc = verso_camera(pl, W, H, i_s, i_g, i_p, po)
                staccato = angolo >= STACCO_ANGOLO_MIN or vc
                # "Braccio teso" (senza vedere la mano) e' piu' severo: dritto e ben staccato
                teso = braccio_dritto(sp, go, po) and angolo >= STACCO_ANGOLO_MIN + 20
                avambraccio = math.hypot(po[0] - go[0], po[1] - go[1])
                lato = max(160, int(2.2 * avambraccio))
                centro = (po[0] + 0.35 * (po[0] - go[0]), po[1] + 0.35 * (po[1] - go[1]))
                pts = mano_da_ritaglio(hands_rit, rgb, centro, lato, po)

                if pts is not None:
                    indice, altre = dita_estese(pts)
                    if indice and not altre and staccato:
                        gesto = "Pointing"
                    elif teso and indice:
                        gesto = "Braccio teso"
                    else:
                        gesto = "Altro"
                    punta = pts[INDICE_TIP]
                elif teso:
                    gesto = "Braccio teso"
                    punta = Punto(*po)
                else:
                    continue

                record.append({
                    "nome": nome_visto(nome_anat), "gesto": gesto, "pts": pts, "braccio": teso,
                    "staccato": staccato, "spalla": sp, "verso_camera": vc,
                    "arto": (sp, go, po), "base": go, "punta": (punta.x, punta.y),
                })

            # Strada 2: la posa a volte sbaglia il braccio (persona seduta, di profilo, mano
            # alzata): cerco le mani anche in una zona ingrandita attorno a tutta la persona
            if sum(1 for r in record if r["pts"] is not None) < 2:
                centro_sp, giu, lung = geometria_busto(pl, W, H)
                centro_busto = centro_sp + giu * lung / 2
                for pts in mani_da_roi(hands_roi, rgb, centro_busto, max(ROI_FATTORE * lung, 320)):
                    polso = (pts[POLSO].x, pts[POLSO].y)
                    doppia = any(r["pts"] is not None and
                                 math.hypot(polso[0] - r["pts"][POLSO].x,
                                            polso[1] - r["pts"][POLSO].y) < 0.25 * lung
                                 for r in record)
                    if doppia:
                        continue
                    # lato = spalla piu' vicina alla mano
                    d_sx = math.hypot(polso[0] - pl[11].x * W, polso[1] - pl[11].y * H)
                    d_dx = math.hypot(polso[0] - pl[12].x * W, polso[1] - pl[12].y * H)
                    i_s, nome_anat = (11, "Sinistra") if d_sx <= d_dx else (12, "Destra")
                    i_g, i_p = (13, 15) if i_s == 11 else (14, 16)
                    vc = verso_camera(pl, W, H, i_s, i_g, i_p, polso)
                    staccato = stacco_braccio(pl, W, H, i_s, polso) >= STACCO_ANGOLO_MIN or vc
                    indice, altre = dita_estese(pts)
                    record.append({
                        "nome": nome_visto(nome_anat),
                        "gesto": "Pointing" if (indice and not altre and staccato) else "Altro",
                        "pts": pts, "braccio": False, "arto": None, "staccato": staccato,
                        "spalla": (pl[i_s].x * W, pl[i_s].y * H), "verso_camera": vc,
                        "base": (pts[INDICE_MCP].x, pts[INDICE_MCP].y),
                        "punta": (pts[INDICE_TIP].x, pts[INDICE_TIP].y),
                    })

    # Strada 3: corpo non visibile (persona molto vicina, es. webcam): mani sull'immagine intera
    if pl is None:
        ris = hands_pieno.process(rgb)
        if ris.multi_hand_landmarks:
            for mano, info in zip(ris.multi_hand_landmarks, ris.multi_handedness):
                pts = [Punto(p.x * W, p.y * H) for p in mano.landmark]
                sinistra = info.classification[0].label == "Left"
                if not specchio:  # MediaPipe presume un'immagine specchiata
                    sinistra = not sinistra
                nome = "Sinistra" if sinistra else "Destra"
                indice, altre = dita_estese(pts)
                record = [r for r in record if r["nome"] != nome]
                record.append({
                    "nome": nome, "gesto": "Pointing" if (indice and not altre) else "Altro",
                    "pts": pts, "braccio": False, "arto": None, "staccato": True,
                    "base": (pts[INDICE_MCP].x, pts[INDICE_MCP].y),
                    "punta": (pts[INDICE_TIP].x, pts[INDICE_TIP].y),
                })

    # Un solo record per lato: vince il gesto piu' significativo
    priorita = {"Pointing": 0, "Braccio teso": 1, "Altro": 2}
    migliori = {}
    for r in record:
        v = migliori.get(r["nome"])
        if v is None or priorita[r["gesto"]] < priorita[v["gesto"]]:
            migliori[r["nome"]] = r
    return list(migliori.values()), corpo
