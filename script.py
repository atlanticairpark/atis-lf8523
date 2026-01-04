import requests
import os
import re
import asyncio
import edge_tts
import time
import json

STATIONS = ["LFBH", "LFRI"]

def formater_chiffre_fr(n):
    n_str = str(n).replace('-', '')
    if n_str == "1": return "unité"
    return n_str.lstrip('0') if len(n_str) > 1 and n_str.startswith('0') else n_str

def obtenir_donnees_moyennes():
    temps, rosees, qnhs, vents_dir, vents_spd, rafales = [], [], [], [], [], []
    h_tele = "--:--"
    for icao in STATIONS:
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                lines = res.text.split('\n')
                if len(lines) < 2: continue
                metar = lines[1]
                time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
                if time_match: h_tele = f"{time_match.group(2)}:{time_match.group(3)}"
                tr_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
                if tr_match:
                    temps.append(int(tr_match.group(1).replace('M', '-')))
                    rosees.append(int(tr_match.group(2).replace('M', '-')))
                q_match = re.search(r'Q(\d{4})', metar)
                if q_match: qnhs.append(int(q_match.group(1)))
                w_match = re.search(r' ([0-9]{3}|VRB)(\d{2})(G\d{2})?KT', metar)
                if w_match:
                    direction = w_match.group(1)
                    vitesse = int(w_match.group(2))
                    if direction != "VRB": vents_dir.append(int(direction))
                    vents_spd.append(vitesse)
                    if w_match.group(3): rafales.append(int(w_match.group(3).replace('G', '')))
        except: continue

    if not vents_spd or not qnhs: return None

    m_t = round(sum(temps)/len(temps)) if temps else 0
    m_r = round(sum(rosees)/len(rosees)) if rosees else 0
    m_q = round(sum(qnhs)/len(qnhs))
    m_wd = round(sum(vents_dir)/len(vents_dir)) if vents_dir else None
    m_ws = round(sum(vents_spd)/len(vents_spd))
    max_g = max(rafales) if rafales else None

    return {
        "heure_metar": h_tele, "qnh": str(m_q), 
        "q_audio_fr": " ".join([formater_chiffre_fr(c) for c in list(str(m_q))]),
        "temp_visu": str(m_t), "dew_visu": str(m_r),
        "t_audio_fr": (("moins " if m_t < 0 else "") + formater_chiffre_fr(abs(m_t))),
        "d_audio_fr": (("moins " if m_r < 0 else "") + formater_chiffre_fr(abs(m_r))),
        "w_dir_visu": f"{str(m_wd).zfill(3) if m_wd else 'VRB'}/{m_ws}" + (f"G{max_g}" if max_g else ""),
        "w_audio_fr": f"vent {m_wd if m_wd else 'variable'} degrés, {m_ws} nœuds" + (f" avec rafales à {max_g}" if max_g else "")
    }

def scanner_notams():
    firs = ["LFRR", "LFFF", "LFEE", "LFMM"]
    status = {"R147": "pas d'information", "R45A": "pas d'information", "DEBUG": "Aucun NOTAM Z0691 trouvé"}
    
    for fir in firs:
        try:
            url = f"https://api.allorigins.win/get?url=" + requests.utils.quote(f"https://notams.aim.faa.gov/notamSearch/search?searchType=0&designators={fir}&sortOrder=0")
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                content = res.json().get('contents', '{}')
                data = json.loads(content)
                
                for notam in data.get("notamList", []):
                    msg = (notam.get("traditionalMessage", "") + notam.get("icaoMessage", "")).upper()
                    
                    # TEST DIRECT DU NUMERO
                    if "Z0691" in msg:
                        status["DEBUG"] = f"Z0691 TROUVÉ ! Texte: {msg[:100]}..."
                        # Si trouvé, on force l'extraction pour R45A
                        match = re.search(r"(\d{4})[-/](\d{4})", msg)
                        if match:
                            status["R45A"] = f"active de {match.group(1)[:2]}:{match.group(1)[2:]} à {match.group(2)[:2]}:{match.group(2)[2:]}"

                    # RECHERCHE CLASSIQUE
                    for zone in ["R147", "R45A"]:
                        if status[zone] == "pas d'information" and zone in msg:
                            m = re.search(r"(\d{4})[-/](\d{4})", msg)
                            if m: status[zone] = f"active de {m.group(1)[:2]}:{m.group(1)[2:]} à {m.group(2)[:2]}:{m.group(2)[2:]}"
        except: continue
    return status

async def generer_audio(vocal_fr):
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural", rate="+5%").save("atis.mp3")

async def executer_veille():
    m = obtenir_donnees_moyennes()
    notams = scanner_notams()
    if not m: return

    # AUDIO
    notam_fr = f"Zone R 147 : {notams['R147']}. Zone R 45 alpha : {notams['R45A']}."
    txt_fr = f"Atlantic Air Park, observation de {m['heure_metar'].replace(':',' heures ')}. {m['w_audio_fr']}. QNH {m['q_audio_fr']}. {notam_fr}"
    await generer_audio(txt_fr)

    ts = int(time.time())
    html_content = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATIS LF8523</title>
    <style>
        body {{ font-family: sans-serif; text-align: center; padding: 20px; background: #121212; color: #e0e0e0; }}
        .card {{ background: #1e1e1e; padding: 25px; border-radius: 15px; border: 1px solid #333; }}
        .alert-section {{ text-align: left; background: rgba(255, 204, 0, 0.1); border-left: 4px solid #ffcc00; padding: 15px; margin: 20px 0; }}
        .debug {{ color: #ff4d4d; font-size: 0.8em; margin-top: 20px; }}
    </style></head><body><div class="card">
    <h1>ATIS LF8523</h1>
    <div class="alert-section">
        <div>⚠️ R147 : {notams['R147']}</div>
        <div style="color:#4dabff;">⚠️ R45A : {notams['R45A']}</div>
    </div>
    <audio controls><source src="atis.mp3?v={ts}" type="audio/mpeg"></audio>
    <div class="debug">🔍 Statut détection : {notams['DEBUG']}</div>
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__":
    asyncio.run(executer_veille())
