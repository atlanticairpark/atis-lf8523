import requests
import os
import re
import asyncio
import edge_tts

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Textes
INFOS_FR = "Piste en herbe zéro huit, deux six fermée cause travaux. Prudence. Péril aviaire."
INFOS_EN = "Grass runway zero eight, two six, closed due to works. Caution. Bird hazard."

def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        metar = response.text.split('\n')[1]
        time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
        h_tele = f"{time_match.group(2)}:{time_match.group(3)}"
        
        q_match = re.search(r'Q(\d{4})', metar)
        q_val = q_match.group(1) if q_match else "1013"
        q_audio = ", ".join(list(q_val))

        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        w_match = re.search(r' (\d{3})(\d{2})KT', metar)
        
        return {
            "heure_metar": h_tele,
            "qnh": int(q_val),
            "q_audio": q_audio,
            "temp": int(t_match.group(1).replace('M', '-')),
            "dew": int(t_match.group(2).replace('M', '-')),
            "w_dir": int(w_match.group(1)) if w_match else 0,
            "w_spd": int(w_match.group(2)) if w_match else 0
        }
    except: return None

async def generer_audio(vocal_fr, vocal_en):
    # Création des fichiers audio avec Henri et Thomas
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural").save("fr.mp3")
    await edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural").save("en.mp3")
    
    # Fusion propre
    with open("atis.mp3", "wb") as f:
        for fname in ["fr.mp3", "en.mp3"]:
            with open(fname, "rb") as fd:
                f.write(fd.read())
    
    # Nettoyage des fichiers temporaires
    if os.path.exists("fr.mp3"): os.remove("fr.mp3")
    if os.path.exists("en.mp3"): os.remove("en.mp3")

async def executer_veille():
    m = obtenir_metar("LFBH")
    if not m: return

    vocal_fr = (f"Atlantic Air Park. Observation de {m['heure_metar'].replace(':',' heures ')} UTC. "
                f"Vent {m['w_dir']:03.0f} degrés, {m['w_spd']:.0f} nœuds. Température {m['temp']:.0f} degrés. "
                f"Point de rosée {m['dew']:.0f} degrés. Q N H {m['q_audio']}. {INFOS_FR}")
    
    vocal_en = (f"Atlantic Air Park. Observation at {m['heure_metar'].replace(':',' ')} UTC. "
                f"Wind {m['w_dir']:03.0f} degrees, {m['w_spd']:.0f} knots. Temperature {m['temp']:.0f} degrees. "
                f"Dew point {m['dew']:.0f} degrees. Q, N, H, {m['q_audio']}. {INFOS_EN}")

    # ATTENDRE que l'audio soit fini
    await generer_audio(vocal_fr, vocal_en)

    # HTML
    html_content = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ATIS LF8523</title>
    <style>body{{font-family:sans-serif;text-align:center;padding:20px;background:#1a1a1a;color:white;}}
    .card{{background:#2d2d2d;padding:30px;border-radius:20px;max-width:450px;margin:auto;border:1px solid #444;}}
    h1{{color:#4dabff;}} .data{{font-size:1.4em;font-weight:bold;margin:15px 0;border-bottom:1px solid #444;}}
    audio{{width:100%;margin-top:25px;filter:invert(100%);}}</style></head>
    <body><div class="card"><h1>LF8523 ATIS</h1><p>Atlantic Air Park</p>
    <div class="data">⌚ {m['heure_metar']} UTC</div>
    <div class="data">🌬 {m['w_dir']:03.0f}° / {m['w_spd']:.0f} kt</div>
    <div class="data">🌡 {m['temp']:.0f}°C</div>
    <div class="data">💎 QNH {m['qnh']} hPa</div>
    <audio controls autoplay><source src="atis.mp3" type="audio/mpeg"></audio>
    <p style="color:#ffcc00; font-weight:bold;">{INFOS_FR}</p></div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    # Lancement correct de la boucle asynchrone
    asyncio.run(executer_veille())
    
