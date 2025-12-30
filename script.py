import requests
import os
import re
import asyncio
import edge_tts

# Configuration Telegram
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Textes de base (utilisés pour l'audio et l'affichage)
REMARQUE_1 = "Piste en herbe 08/26 fermée cause travaux"
REMARQUE_2 = "Prudence"
REMARQUE_3 = "Péril aviaire"

def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        metar = response.text.split('\n')[1]
        
        # Extraction Heure
        time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
        h_tele = f"{time_match.group(2)}:{time_match.group(3)}"
        
        # Extraction QNH et préparation audio (chiffre par chiffre)
        q_match = re.search(r'Q(\d{4})', metar)
        q_val = q_match.group(1) if q_match else "1013"
        q_audio = ", ".join(list(q_val))

        # Extraction Température et Point de rosée
        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        temp = t_match.group(1).replace('M', '-')
        dew = t_match.group(2).replace('M', '-')
        
        # Extraction Vent
        w_match = re.search(r' (\d{3})(\d{2})KT', metar)
        w_dir = w_match.group(1) if w_match else "000"
        w_spd = w_match.group(2) if w_match else "0"
        
        return {
            "heure_metar": h_tele,
            "qnh": q_val,
            "q_audio": q_audio,
            "temp": temp,
            "dew": dew,
            "w_dir": w_dir,
            "w_spd": w_spd
        }
    except Exception as e:
        print(f"Erreur METAR: {e}")
        return None

def scanner_notams():
    # Par défaut, on reste prudent sur l'affichage
    resultats = {"R147": "Pas d'info"}
    try:
        # On interroge la FIR de Brest/Nantes (LFRR) pour la R147
        res = requests.get("https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html"), timeout=15)
        texte = res.text.upper()
        
        if "R147" in texte:
            # Recherche d'horaires type 0800 TO 1200
            horaires = re.findall(r"R147.*?(\d{4}.*?TO.*?\d{4})", texte)
            if horaires:
                resultats["R147"] = f"ACTIVE de {horaires[0].replace('TO', 'à')}"
            else:
                resultats["R147"] = "ACTIVE (Horaires : voir NOTAM)"
    except:
        pass
    return resultats

async def generer_audio(vocal_fr, vocal_en):
    # Génération des deux langues
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural").save("fr.mp3")
    await edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural").save("en.mp3")
    
    # Fusion des fichiers
    with open("atis.mp3", "wb") as f:
        for fname in ["fr.mp3", "en.mp3"]:
            with open(fname, "rb") as fd:
                f.write(fd.read())
    
    # Suppression des fichiers temporaires
    for f in ["fr.mp3", "en.mp3"]:
        if os.path.exists(f): os.remove(f)

async def executer_veille():
    m = obtenir_metar("LFBH")
    notams = scanner_notams()
    if not m: return

    # --- Préparation des textes audio ---
    # Français (Diction naturelle)
    txt_fr = (f"Atlantic Air Park. Observation de {m['heure_metar'].replace(':',' heures ')} UTC. "
              f"Vent {
