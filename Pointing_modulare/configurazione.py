"""Costanti del rilevatore e impostazioni del video."""




# ----------------------------- Configurazione -----------------------------
VIDEO_PREDEFINITO = None    # oppure "/percorso/video.avi" (utile col tasto Play di VS Code)
LARGHEZZA_CAMERA, ALTEZZA_CAMERA = 1280, 720
LARGHEZZA_VISTA_MAX = 1280  # dimensioni massime dell'immagine mostrata
ALTEZZA_VISTA_MAX = 800
FRAME_SMOOTHING = 9         # frame usati per stabilizzare il risultato
TOLLERANZA_ASSENZA = 8      # frame di assenza prima di chiudere un evento
MIN_DURATA_RIEPILOGO = 0.3  # secondi: eventi piu' brevi non compaiono nel riepilogo
NOME_FINESTRA = "Rilevatore di pointing"


GESTI_ATTIVI = ("Pointing", "Braccio teso")

# Landmark delle mani
POLSO = 0
INDICE_MCP, INDICE_PIP, INDICE_TIP = 5, 6, 8
MEDIO_MCP, MEDIO_PIP, MEDIO_TIP = 9, 10, 12
ANULARE_PIP, ANULARE_TIP = 14, 16
MIGNOLO_PIP, MIGNOLO_TIP = 18, 20

# (spalla, gomito, polso) di ogni braccio, con etichetta anatomica
BRACCIA = {"Sinistra": (11, 13, 15), "Destra": (12, 14, 16)}

# Corpo intero SENZA testa (indici MediaPipe Pose: 11-12 spalle, 13-14 gomiti, 15-16 polsi,
# 23-24 anche, 25-26 ginocchia, 27-28 caviglie). I landmark del viso (0-10) non si usano.
SEGMENTI_CORPO = [(11, 12), (11, 23), (12, 24), (23, 24),          # busto
                  (11, 13), (13, 15), (12, 14), (14, 16),          # braccia
                  (23, 25), (25, 27), (24, 26), (26, 28)]          # gambe
VISIBILITA_MIN = 0.5

# Vincolo "braccio staccato dal corpo" (pointing valido solo se il braccio e' lontano dal busto)
STACCO_ANGOLO_MIN = 40      # gradi minimi tra braccio (spalla->polso) e asse del busto (in 2D)
ROI_FATTORE = 3.6           # lato della zona di ricerca mani = fattore x lunghezza del busto
POSTER = ("Cuore", "Sole")  # poster da segnare con il mouse, nell'ordine
BERSAGLIO_CAMERA = "Dietro la camera"   # poster dietro la telecamera (non e' nell'immagine)
TOLLERANZA_POSTER = 25      # gradi di scarto massimo tra direzione del braccio e poster

# Codici delle frecce restituiti da cv2.waitKeyEx (cambiano da sistema a sistema)
FRECCIA_SX = (2424832, 63234, 65361, 2)
FRECCIA_DX = (2555904, 63235, 65363, 3)

DIREZIONI = ["destra", "alto-destra", "alto", "alto-sinistra",
             "sinistra", "basso-sinistra", "basso", "basso-destra"]
