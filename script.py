import requests
import os
import re
import asyncio
import edge_tts
import time

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
        "q_audio_en": " ".join(list(str(m_q))),
        "temp_visu": str(m_t), "dew_visu": str(m_r),
        "t_audio_fr": (("moins " if m_t < 0 else "") + formater_chiffre_fr(abs(m_t))),
        "d_audio_fr": (("moins " if m_r < 0 else "") + formater_chiffre_fr(abs(m_r))),
        "t_audio_en": (("minus " if m_t < 0 else "") + str(abs(m_t))),
        "d_audio_en": (("minus " if m_r < 0 else "") + str(abs(m_r))),
        "w_dir_visu": f"{str(m_wd).zfill(3) if m_wd else 'VRB'}/{m_ws}" + (f"G{max_g}" if max_g else ""),
        "w_audio_fr": f"vent {m_wd if m_wd else 'variable'} degrés, {m_ws} nœuds" + (f" avec rafales à {max_g}" if max_g else ""),
        "w_audio_en": f"wind {m_wd if m_wd else 'variable'} degrees, {m_ws} knots" + (f" gusting {max_g}" if max_g else "")
    }

def scanner_notams():
    status = {"R147": "pas d'information", "R45A": "pas d'information", "DEBUG": ""}
    # On multiplie les sources : FAA et NotamInfo
    urls = [
        "https://notaminfo.com/france/notams",
        "https://www.notams.faa.gov/common/icao/LFFF.html",
        "https://www.notams.faa.gov/common/icao/LFRR.html"
    ]
    
    combined_text = ""
    for u in urls:
        try:
            res = requests.get("https://api.allorigins.win/get?url=" + requests.utils.quote(u), timeout=10)
            if res.status_code == 200:
                combined_text += re.sub(r'<[^>]+>', ' ', res.text.upper()) + " "
        except: continue
    
    combined_text = " ".join(combined_text.split())
    status["DEBUG"] = f"Scan OK ({len(combined_text)} car.)"

    for zone in ["R147", "R45A"]:
        # Recherche ultra-permissive : Nom de zone + n'importe quoi + (HHMM-HHMM ou HHMM/HHMM)
        match = re.search(rf"{zone}.*?(\d{{4}}[-/]\d{{4}})", combined_text)
        if match:
            t = match.group(1).replace('/', '-')
            status[zone] = f"active de {t[:2]}:{t[2:4]} à {t[-4:-2]}:{t[-2:]}"
        elif zone in combined_text:
            status[zone] = "citée (vérifier SIA)"
            
    return status

async def generer_audio(vocal_fr, vocal_en):
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural", rate="+5%").save("fr.mp3")
    await edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural", rate="+10%").save("en.mp3")
    with open("atis.mp3", "wb") as f:
        for fname in ["fr.mp3", "en.mp3"]:
            if os.path.exists(fname):
                with open(fname, "rb") as fd: f.write(fd.read())
    if os.path.exists("fr.mp3"): os.remove("fr.mp3")
    if os.path.exists("en.mp3"): os.remove("en.mp3")

async def executer_veille():
    m = obtenir_donnees_moyennes()
    notams = scanner_notams()
    if not m: return

    remarques_raw = os.getenv("ATIS_REMARQUES", "Piste en herbe 08/26 fermée cause travaux | Prudence :: Grass runway 08/26 closed due to works | Caution")
    partie_fr, partie_en = remarques_raw.split("::") if "::" in remarques_raw else (remarques_raw, "Caution")
    
    # Audio FR
    notam_fr = f"Zone R 147 : {notams['R147']}. Zone R 45 alpha : {notams['R45A']}."
    txt_fr = (f"Atlantic Air Park, observation de {m['heure_metar'].replace(':',' heures ')}. "
              f"{m['w_audio_fr']}. Température {m['t_audio_fr']} degrés. Point de rosée {m['d_audio_fr']} degrés. "
              f"Q N H {m['q_audio_fr']} hectopascals. {partie_fr}. {notam_fr}")

    # Audio EN
    txt_en = (f"Atlantic Air Park observation at {m['heure_metar'].replace(':',' ')}. "
              f"{m['w_audio_en']}. Temperature {m['t_audio_en']} degrees. Dew point {m['d_audio_en']} degrees. "
              f"Q N H {m['q_audio_en']} hectopascals. {partie_en}. Check NOTAM for R 147 and R 45 alpha.")

    await generer_audio(txt_fr, txt_en)
    ts = int(time.time())

    # HTML
    html_content = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATIS LF8523</title>
    <style>
        body {{ font-family: sans-serif; text-align: center; padding: 20px; background: #121212; color: #e0e0e0; }}
        .card {{ background: #1e1e1e; padding: 25px; border-radius: 15px; max-width: 500px; margin: auto; border: 1px solid #333; }}
        h1 {{ color: #fff; }} .subtitle {{ color: #4dabff; font-weight: bold; margin-bottom: 25px; }}
        .data-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }}
        .data-item {{ background: #2a2a2a; padding: 15px; border-radius: 10px; border: 1px solid #3d3d3d; }}
        .label {{ font-size: 0.75em; color: #888; text-transform: uppercase; }}
        .value {{ font-size: 1.2em; font-weight: bold; color: #fff; }}
        .alert-section {{ text-align: left; background: rgba(255, 204, 0, 0.1); border-left: 4px solid #ffcc00; padding: 15px; margin-bottom: 25px; }}
        .alert-line {{ color: #ffcc00; font-weight: bold; font-size: 0.9em; margin-bottom: 8px; }}
        audio {{ width: 100%; filter: invert(90%); }}
    </style></head><body><div class="card">
    <h1>ATIS LF8523</h1><div class="subtitle">Atlantic Air Park</div>
    <div class="data-grid">
        <div class="data-item"><div class="label">Heure (UTC)</div><div class="value">⌚ {m['heure_metar']}Z</div></div>
        <div class="data-item"><div class="label">Vent</div><div class="value">🌬 {m['w_dir_visu']}kt</div></div>
        <div class="data-item"><div class="label">Temp / Rosée</div><div class="value">🌡 {m['temp_visu']}° / {m['dew_visu']}°</div></div>
        <div class="data-item"><div class="label">QNH</div><div class="value">💎 {m['qnh']} hPa</div></div>
    </div>
    <div class="alert-section">
        <div class="alert-line">⚠️ RTBA R147 : {notams['R147']}</div>
        <div class="alert-line" style="color:#4dabff;">⚠️ RTBA R45A : {notams['R45A']}</div>
    </div>
    <audio controls><source src="atis.mp3?v={ts}" type="audio/mpeg"></audio>
    <div style="font-size:0.7em; color:#444; margin-top:15px;">{notams['DEBUG']}</div>
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__":
    asyncio.run(executer_veille())
