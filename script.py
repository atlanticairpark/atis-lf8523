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
    status = {"R147": "pas d'information", "R45A": "pas d'information"}
    try:
        url = "https://api.allorigins.win/get?url=" + requests.utils.quote("https://notaminfo.com/france/notams")
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            txt = res.text.upper()
            for zone in ["R147", "R45A"]:
                match = re.search(rf"{zone}.*?(\d{{4}}[-/]\d{{4}})", txt)
                if match:
                    t = match.group(1).replace('/', '-')
                    status[zone] = f"active de {t[:2]}:{t[2:4]} à {t[-4:-2]}:{t[-2:]}"
    except: pass
    return status

async def generer_audio(vocal_fr, vocal_en):
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural", rate="+5%").save("fr.mp3")
    await edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural", rate="+10%").save("en.mp3")
    with open("atis.mp3", "wb") as f:
        for fname in ["fr.mp3", "en.mp3"]:
            if os.path.exists(fname):
                with open(fname, "rb") as fd: f.write(fd.read())
    for f in ["fr.mp3", "en.mp3"]:
        if os.path.exists(f): os.remove(f)

async def executer_veille():
    m = obtenir_donnees_moyennes()
    notams = scanner_notams()
    if not m: return

    # Gestion des remarques bilingues (Secret GitHub ou défaut)
    remarques_raw = os.getenv("ATIS_REMARQUES", "Piste en herbe 08/26 fermée cause travaux | Prudence :: Grass runway 08/26 closed due to work | Caution")
    partie_fr, partie_en = remarques_raw.split("::") if "::" in remarques_raw else (remarques_raw, "Caution")
    
    # Audio FR
    audio_notam_fr = f"Zone R 147 : {notams['R147']}. Zone R 45 alpha : {notams['R45A']}."
    txt_fr = (f"Atlantic Air Park, observation de {m['heure_metar'].replace(':',' heures ')}. "
              f"{m['w_audio_fr']}. Température {m['t_audio_fr']} degrés. Rosée {m['d_audio_fr']} degrés. "
              f"Q N H {m['q_audio_fr']} hectopascals. {partie_fr}. {audio_notam_fr}")

    # Audio EN
    audio_notam_en = f"R 147 status: {notams['R147']}. R 45 alpha status: {notams['R45A']}."
    txt_en = (f"Atlantic Air Park observation at {m['heure_metar'].replace(':',' ')}. "
              f"{m['w_audio_en']}. Temperature {m['t_audio_en']} degrees. Dew point {m['d_audio_en']} degrees. "
              f"Q N H {m['q_audio_en']} hectopascals. {partie_en}. {audio_notam_en}")

    await generer_audio(txt_fr, txt_en)
    ts = int(time.time())

    # HTML Complet Restauré
    html_content = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATIS LF8523</title>
    <style>
        body {{ font-family: sans-serif; text-align: center; padding: 20px; background: #121212; color: #e0e0e0; }}
        .card {{ background: #1e1e1e; padding: 25px; border-radius: 15px; max-width: 500px; margin: auto; border: 1px solid #333; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
        h1 {{ color: #fff; margin-bottom: 5px; }}
        .subtitle {{ color: #4dabff; font-weight: bold; margin-bottom: 25px; text-transform: uppercase; font-size: 0.9em; }}
        .data-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }}
        .data-item {{ background: #2a2a2a; padding: 15px; border-radius: 10px; border: 1px solid #3d3d3d; }}
        .label {{ font-size: 0.75em; color: #888; text-transform: uppercase; }}
        .value {{ font-size: 1.2em; font-weight: bold; color: #fff; }}
        .alert-section {{ text-align: left; background: rgba(255, 204, 0, 0.1); border-left: 4px solid #ffcc00; padding: 15px; margin-bottom: 25px; }}
        .alert-line {{ color: #ffcc00; font-weight: bold; font-size: 0.9em; margin-bottom: 8px; }}
        audio {{ width: 100%; filter: invert(90%); margin-bottom: 20px; }}
        .btn-refresh {{ background: #333; color: #ccc; border: 1px solid #444; padding: 12px 20px; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; transition: 0.3s; }}
        .btn-refresh:hover {{ background: #444; color: #fff; }}
        .disclaimer {{ font-size: 0.7em; color: #666; margin-top: 30px; line-height: 1.4; text-align: justify; border-top: 1px solid #333; padding-top: 15px; }}
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
        <div class="alert-line" style="margin-top:10px; border-top: 1px solid rgba(255,204,0,0.2); padding-top:10px;">📋 {partie_fr.split('|')[0]}</div>
    </div>
    <audio controls><source src="atis.mp3?v={ts}" type="audio/mpeg"></audio>
    <button class="btn-refresh" onclick="window.location.reload()">🔄 ACTUALISER LES DONNÉES</button>
    <div class="disclaimer"><b>DISCLAIMER :</b> Données issues de sources METAR/NOTAM automatisées. Utilisation à titre informatif uniquement. Vérifiez les sources officielles du SIA (NOTAM & AZBA) avant tout vol.</div>
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__":
    asyncio.run(executer_veille())
