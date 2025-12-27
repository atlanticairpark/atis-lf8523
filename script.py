import requests
import os
import re
from datetime import datetime
from gtts import gTTS
from io import BytesIO

# --- CONFIGURATION ---
INFOS_FR = "Piste zéro huit, deux six en herbe fermée cause travaux. Prudence. Péril aviaire."
INFOS_EN = "Grass runway zero eight, two six, closed due to works. Caution. Bird hazard."

def executer_veille():
    m1 = obtenir_metar("LFBH")
    m2 = obtenir_metar("LFRI")
    if not m1: return

    # Calculs moyennes
    q_moy = (m1['qnh'] + m2['qnh']) / 2
    t_moy = (m1['temp'] + m2['temp']) / 2
    d_moy = (m1['dew'] + m2['dew']) / 2
    wd, ws = (m1['w_dir'] + m2['w_dir']) / 2, (m1['w_spd'] + m2['w_spd']) / 2

    # --- SCRIPT VOCAL FRANÇAIS (Accent FR) ---
    txt_fr = (f"Atlantic Air Park. Observation de {m1['heure_vocal']} UTC. "
              f"Vent {wd:03.0f} degrés, {ws:.0f} nœuds. "
              f"Température {t_moy:.0f} degrés. Point de rosée {d_moy:.0f} degrés. "
              f"Q N H {q_moy:.0f} hectopascals. {INFOS_FR}")

    # --- SCRIPT VOCAL ANGLAIS (Accent UK) ---
    # On épèle QNH pour l'anglais pour que ce soit plus clair
    txt_en = (f"Atlantic Air Park. Observation at {m1['heure_metar'].replace(':', ' ')} UTC. "
              f"Wind {wd:03.0f} degrees, {ws:.0f} knots. "
              f"Temperature {t_moy:.0f} degrees. Dew point {d_moy:.0f} degrees. "
              f"Q, N, H, {q_moy:.0f}. {INFOS_EN}")

    # Génération des deux voix
    tts_fr = gTTS(text=txt_fr, lang='fr')
    tts_en = gTTS(text=txt_en, lang='en', tld='co.uk') # Voix britannique

    # Fusion des fichiers (on les enregistre l'un après l'autre dans le même fichier)
    with open("atis.mp3", "wb") as f:
        tts_fr.write_to_fp(f)
        # On peut même ajouter un petit silence ici si on voulait, 
        # mais réécrire à la suite fonctionne déjà bien
        tts_en.write_to_fp(f)

    # ... reste du code pour index.html et Telegram ...
