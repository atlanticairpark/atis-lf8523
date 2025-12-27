import requests
import os
import re
from datetime import datetime, timezone
from gtts import gTTS

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

INFOS_FR = "Piste zéro huit, deux six en herbe fermée cause travaux. Prudence péril aviaire."
INFOS_EN = "Grass runway zero eight, two six closed due to works. Bird hazard reported."

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

def executer_veille():
    m1, m2 = obtenir_metar("LFBH"), obtenir_metar("LFRI")
    if not m1: return
    
    q_moy = (m1['qnh'] + m2['qnh']) / 2
    t_moy = (m1['temp'] + m2['temp']) / 2
    d_moy = (m1['dew'] + m2['dew']) / 2
    wd, ws = (m1['w_dir'] + m2['w_dir']) / 2, (m1['w_spd'] + m2['w_spd']) / 2

    vocal = (f"Atlantic Air Park. Observation de {m1['heure_vocal']} UTC. "
             f"Vent {wd:03.0f} degrés, {ws:.0f} nœuds. Température {t_moy:.0f} degrés. "
             f"Point de rosée {d_moy:.0f} degrés. Q N H {q_moy:.0f}. {INFOS_FR}")
    
    # Zones NOTAM
    zones = []
    try:
        res = requests.get("https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html"), timeout=15)
        if "R147" in res.text.upper(): zones.append("R 147")
        if "R45A" in res.text.upper(): zones.append("R 45 Alpha")
    except: pass
    if zones: vocal += f" Attention, zones actives : {', '.join(zones)}."

    # Génération Audio
    tts = gTTS(text=vocal, lang='fr')
    tts.save("atis.mp3")

    # CRÉATION DE LA PAGE WEB (index.html)
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ATIS LF8523</title>
        <style>
            body {{ font-family: sans-serif; text-align: center; padding: 20px; background: #f0f4f8; }}
            .card {{ background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 400px; margin: auto; }}
            h1 {{ color: #1a3a5f; }}
            .data {{ font-size: 1.2em; margin: 10px 0; color: #333; }}
            audio {{ width: 100%; margin-top: 20px; }}
            .footer {{ font-size: 0.8em; color: #666; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>LF8523 - ATIS</h1>
            <p><strong>Atlantic Air Park</strong></p>
            <hr>
            <div class="data">⌚ Obs : {m1['heure_metar']} UTC</div>
            <div class="data">🌬 {wd:03.0f}° / {ws:.0f} kt</div>
            <div class="data">🌡 {t_moy:.0f}°C (DP:{d_moy:.0f}°C)</div>
            <div class="data">💎 QNH {q_moy:.0f} hPa</div>
            <div class="data" style="color:red;">{'⚠️ Zones : ' + ', '.join(zones) if zones else '✅ Zones : RAS'}</div>
            <audio controls><source src="atis.mp3" type="audio/mpeg"></audio>
            <p style="font-size:0.9em; margin-top:10px;">{INFOS_FR}</p>
        </div>
        <div class="footer">Mis à jour automatiquement toutes les heures</div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # Envoi Telegram
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendAudio", data={"chat_id": CHAT_ID, "caption": f"ATIS LF8523 - {m1['heure_metar']} UTC"}, files={'audio': open("atis.mp3", 'rb')})

if __name__ == "__main__":
    executer_veille()
