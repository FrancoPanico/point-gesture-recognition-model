"""Palette, font e dimensioni grafiche."""

from PIL import ImageFont


LARGHEZZA_UI, ALTEZZA_UI = 1160, 700
MARGINE_UI = 24
ALTEZZA_TESTATA = 64
PANNELLO_VIDEO = (MARGINE_UI, 82, LARGHEZZA_UI - MARGINE_UI - 280, ALTEZZA_UI - MARGINE_UI)
VANO_VIDEO = (PANNELLO_VIDEO[0] + 1, PANNELLO_VIDEO[1] + 44,
              PANNELLO_VIDEO[2], PANNELLO_VIDEO[3] - 106)
PANNELLO_RILEVAMENTO = (PANNELLO_VIDEO[2] + 16, 82, LARGHEZZA_UI - MARGINE_UI, 314)
PANNELLO_EVENTI = (PANNELLO_RILEVAMENTO[0], 330, PANNELLO_RILEVAMENTO[2], PANNELLO_VIDEO[3])

# ------------------------------- Palette (BGR) ----------------------------
def bgr(esadecimale):
    return tuple(reversed(bytes.fromhex(esadecimale)))


SFONDO = bgr("10141C")
PANNELLO = bgr("171D28")
FONDO_VIDEO = bgr("0B0F15")
BORDO = bgr("303A4B")
GRIGLIA = bgr("202938")
SECONDARIO = bgr("202936")
SELEZIONATO = bgr("2A3856")
BORDO_SELEZIONATO = bgr("576DA0")
PRIMARIO = bgr("AEBCFF")
TESTO = bgr("F0F3FA")
TESTO_SEC = bgr("B9C5D6")
TESTO_DIM = bgr("8C9BB1")
TESTO_SCURO = bgr("11182A")
ACCENTO = bgr("69DFC1")        # pointing
FONDO_ACCENTO = bgr("1A3634")
AMBRA = bgr("F1C582")          # braccio teso
FONDO_AMBRA = bgr("392F26")
TRACCIAMENTO = bgr("95A5BD")
ROSSO_LIVE = bgr("EF939B")
OMBRA = bgr("0C111A")

# --------------------------------- Font -----------------------------------
FONT_REGOLARI = ("Inter-Regular.ttf", "/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Supplemental/Arial.ttf", "segoeui.ttf", "DejaVuSans.ttf")
FONT_GRASSETTO = ("Inter-SemiBold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                  "seguisb.ttf", "DejaVuSans-Bold.ttf") + FONT_REGOLARI
FONT_MONO = ("/System/Library/Fonts/Menlo.ttc", "consola.ttf", "DejaVuSansMono.ttf") + FONT_REGOLARI


def carica_font(dimensione, famiglie=FONT_REGOLARI):
    for percorso in famiglie:
        try:
            return ImageFont.truetype(percorso, dimensione)
        except OSError:
            continue
    try:
        return ImageFont.load_default(dimensione)
    except TypeError:
        return ImageFont.load_default()
