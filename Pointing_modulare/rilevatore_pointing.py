"""
Rilevatore di pointing
======================
Riconosce quando una persona indica qualcosa, da webcam oppure da un video
(per esempio registrato con Azure Kinect), anche mentre fa altro.

Avvio:
    python rilevatore_pointing.py                  # schermata iniziale con i pulsanti
    python rilevatore_pointing.py --video file.avi # apre subito un video

Dentro il programma:
    pulsante "Apri video" (o tasto O)   scegli un video dal computer
    pulsante "Webcam"     (o tasto W)   usa la webcam
    pulsante "Pausa"      (o Spazio)    pausa / riprendi (a fine video: ricomincia)
    pulsante "Poster"     (o tasto P)   segna a mano i poster: il video torna all'inizio e si clicca
                         su cuore e sole (Invio = salta, Esc = annulla)
    pulsanti "Frame −1" / "Frame +1"    un frame indietro / avanti, solo video
                         (tasti A / D, virgola / punto, frecce sinistra / destra)
    pulsante "Tracciamento" (o T)       mostra anche il tracciamento delle mani non in pointing
    clic sulla barra del tempo          salta a un punto del video
    pulsante "Esci"       (o Q / ESC)   chiude

Come funziona sui video (persona lontana, mani piccole):
  1) MediaPipe Pose trova spalla, gomito e polso di ogni braccio
  2) si ingrandisce la zona attorno al polso e li' si cerca la mano; se la posa sbaglia il
     braccio, la mano si cerca anche in una zona ingrandita attorno a tutta la persona
  3) pointing = indice teso e le altre dita chiuse
     + VINCOLO: il braccio deve essere staccato dal corpo (angolo tra braccio e busto,
       calcolato sul corpo intero senza testa; soglia con --stacco-angolo)
  4) se la mano e' troppo sfocata ma il braccio e' alzato e teso, il segnale
     e' "Braccio teso" (probabile pointing)
  5) POSTER: le posizioni segnate con "Poster" sono salvate in <video>_poster.json e
     ricaricate al prossimo avvio. Ogni pointing viene collegato al poster verso cui punta il
     braccio (spalla -> punta del dito, tolleranza --tolleranza-poster). "Dietro la camera" =
     braccio puntato verso la telecamera. Un braccio teso che non punta a nessun poster viene
     scartato (con --solo-poster anche il pointing col dito).
Alla fine viene stampato un riepilogo e salvato un file CSV con tutti gli eventi.
"""


import argparse
import rilevamento
from app import (
    App,
)
from configurazione import (
    STACCO_ANGOLO_MIN,
    TOLLERANZA_POSTER,
    VIDEO_PREDEFINITO,
)


def leggi_argomenti():
    p = argparse.ArgumentParser(description="Rilevatore di pointing da webcam o video.")
    p.add_argument("--video", default=VIDEO_PREDEFINITO,
                   help="apre subito questo video (altrimenti compare la schermata iniziale)")
    p.add_argument("--camera", type=int, default=0, help="indice della webcam (default 0)")
    p.add_argument("--rilevamento", choices=["auto", "pose", "mani"], default="auto",
                   help="pose = posa del corpo + ritaglio sul polso (persona lontana); "
                        "mani = solo mani sull'immagine intera (persona vicina). "
                        "auto: posa del corpo sia per i video sia per la webcam")
    p.add_argument("--pose", type=int, choices=[0, 1, 2], default=1,
                   help="precisione del modello di posa: 0 veloce, 2 preciso (default 1)")
    p.add_argument("--stacco-angolo", type=float, default=STACCO_ANGOLO_MIN,
                   help="angolo minimo (gradi) tra braccio e busto perche' il braccio sia 'staccato' "
                        f"dal corpo (default {STACCO_ANGOLO_MIN})")
    p.add_argument("--tolleranza-poster", type=float, default=TOLLERANZA_POSTER,
                   help="scarto massimo in gradi tra la direzione del braccio e un poster segnato "
                        f"(default {TOLLERANZA_POSTER})")
    p.add_argument("--solo-poster", action="store_true",
                   help="con i poster segnati, scarta anche i pointing col dito che non puntano a nessun poster")
    p.add_argument("--ogni", type=int, default=1,
                   help="elabora un frame ogni N (solo video): piu' veloce")
    p.add_argument("--salva-video", action="store_true", help="salva anche il video con le annotazioni")
    p.add_argument("--nessun-csv", action="store_true", help="non crea il file CSV")
    return p.parse_args()


def main():
    args = leggi_argomenti()
    rilevamento.STACCO_ANGOLO_MIN = args.stacco_angolo
    app = App(args)
    if args.video:
        app.avvia_video(args.video)
    app.esegui()


if __name__ == "__main__":
    main()
