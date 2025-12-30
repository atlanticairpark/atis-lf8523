import requests
import os
import re
import asyncio
import edge_tts
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- TEXTES PHONÉTIQUES ---
INFOS_FR = "Piste zéro huit, deux six en herbe fermée cause travaux. Prudence. Péril aviaire."
INFOS_EN = "Grass runway zero eight, two six, closed due to works. Caution. Bird hazard."

def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        lignes = response.text.split('\n')
        metar = lignes[1]
        time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
        h_tele = f"{time_match.group(2)}:{time_match.group(3)}" if time_match else "??:??"
        h_vocal = f"{time_match.group(2)} heures {time_match.group(3)}" if time_match else "Heure inconnue"
        w_match = re.search(r' (\d{3})(\d{2})KT', metar)
        q_match = re.search(r'Q(\d{4})', metar)
        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        return {
            "heure_metar": h_tele, "heure_vocal": h_vocal,
            "qnh": int(q_match.group(1)) if q_match else 1013,
            "temp": int(t_match.group(1).replace('M', '-')) if t_match else 15,
            "dew": int(t_match.group(2).replace('M', '-')) if t_match else 10,
            "w_dir": int(w_match.group(1)) if w_match else 0, "w_spd": int(w_match.group(2)) if w_match else 0
        }
    except: return None

async def generer_audio(vocal_fr, vocal_en):
    # Génération voix homme FR (Henri)
    communicate_fr = edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural")
    await communicate_fr.save("fr.mp3")
    
    # Génération voix homme UK (Thomas)
    communicate_en = edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural")
    await communicate_en.save("en.mp3")
    
    # Fusion des fichiers
    with open("atis.mp3", "wb") as f:
        f.write(open("fr.mp3", "rb").read())
        f.write(open("en.mp3", "rb").read())

def executer_veille():
    m1, m2 = obtenir_metar("LFBH"), obtenir_metar("LFRI")
    if not m1: return
    
    q_moy = (m1['qnh'] + m2['qnh']) / 2
    t_moy = (m1['temp'] + m2['temp']) / 2
    d_moy = (m1['dew'] + m2['dew']) / 2
    wd, ws = (m1['w_dir'] + m2['w_dir']) / 2, (m1['w_spd'] + m2['w_spd']) / 2

    # --- TEXTE FRANÇAIS ---
    vocal_fr = (f"Atlantic Air Park. Observation de {m1['heure_vocal']} UTC. "
                f"Vent {wd:03.0f} degrés, {ws:.0f} nœuds. Température {t_moy:.0f} degrés. "
                f"Point de rosée {d_moy:.0f} degrés. Q N H {q_moy:.0f} hectopascals. {INFOS_FR}")
    
    # --- TEXTE ANGLAIS ---
    vocal_en = (f"Atlantic Air Park. Observation at {m1['heure_metar'].replace(':', ' ')} UTC. "
                f"Wind {wd:03.0f} degrees, {ws:.0f} knots. Temperature {t_moy:.0f} degrees. "
                f"Dew point {d_moy:.0f} degrees. Q, N, H, {q_moy:.0f}. {INFOS_EN}")

    # Lancement de la génération audio asynchrone
    asyncio.run(generer_audio(vocal_fr, vocal_en))

    # --- GÉNÉRATION HTML ---
    html_content = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ATIS LF8523</title><style>
body {{ font-family: 'Segoe UI', sans-serif; text-align: center; padding: 20px; background: #1a1a1a; color: white; }}
.card {{ background: #2d2d2d; padding: 30px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); max-width: 450px; margin: auto; border: 1px solid #444; }}
h1 {{ color: #4dabff; margin-bottom: 5px; }}
.obs {{ color: #aaa; font-style: italic; margin-bottom: 20px; }}
.data {{ font-size: 1.4em; font-weight: bold; margin: 15px 0; border-bottom: 1px solid #444; padding-bottom: 5px; }}
audio {{ width: 100%; margin-top: 25px; filter: invert(100%); }}
.notam {{ color: #ff6b6b; font-weight: bold; margin-top: 15px; }}
</style></head><body><div class="card"><h1>LF8523 ATIS</h1><p>Atlantic Air Park</p>
<div class="obs">⌚ {m1['heure_metar']} UTC</div>
<div class="data">🌬 {wd:03.0f}° / {ws:.0f} kt</div>
<div class="data">🌡 {t_moy:.0f}°C (DP:{d_moy:.0f}°C)</div>
<div class="data">💎 QNH {q_moy:.0f} hPa</div>
<audio controls autoplay><source src="atis.mp3" type="audio/mpeg"></audio>
<p class="notam">{INFOS_FR}</p></div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # Envoi Telegram
    with open("atis.mp3", 'rb') as a:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendAudio", 
                      data={"chat_id": CHAT_ID, "caption": f"ATIS {m1['heure_metar']} UTC"}, 
                      files={'audio': a})

if __name__ == "__main__":
    executer_veille()
