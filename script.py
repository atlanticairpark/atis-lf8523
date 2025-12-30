import requests
import os
import re
import asyncio
import edge_tts

# Configuration
ICAO = "LFBH" # La Rochelle pour les METAR

def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        metar = response.text.split('\n')[1]
        
        # --- HEURE ---
        time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
        h_tele = f"{time_match.group(2)}:{time_match.group(3)}"
        
        # --- VENT (Gestion CALM, VRB et GUSTS) ---
        w_dir_txt, w_spd_txt = "000", "0"
        w_audio_fr, w_audio_en = "", ""

        if "00000KT" in metar:
            w_dir_txt, w_spd_txt = "CALME", "0"
            w_audio_fr, w_audio_en = "vent calme", "wind calm"
        else:
            w_match = re.search(r' ([A-Z0-9]{3})(\d{2})(G\d{2})?KT', metar)
            if w_match:
                dir_raw = w_match.group(1)
                spd_raw = w_match.group(2).lstrip('0') or "0"
                gust_raw = w_match.group(3)
                
                if dir_raw == "VRB":
                    w_dir_txt, w_audio_fr, w_audio_en = "VRB", "vent variable", "wind variable"
                else:
                    w_dir_txt = dir_raw
                    w_audio_fr, w_audio_en = f"vent {dir_raw} degrés", f"wind {dir_raw} degrees"
                
                if gust_raw:
                    gust_spd = gust_raw.replace('G', '').lstrip('0')
                    w_spd_txt = f"{spd_raw}-{gust_spd}"
                    w_audio_fr += f", {spd_raw} nœuds, rafales {gust_spd} nœuds"
                    w_audio_en += f", {spd_raw} knots, gusts {gust_spd} knots"
                else:
                    w_spd_txt = spd_raw
                    w_audio_fr += f", {spd_raw} nœuds"
                    w_audio_en += f", {spd_raw} knots"

        # --- QNH / TEMP / DEW ---
        q_match = re.search(r'Q(\d{4})', metar)
        q_val = q_match.group(1) if q_match else "1013"
        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        temp = t_match.group(1).replace('M', '-')
        dew = t_match.group(2).replace('M', '-')
        
        return {
            "heure_metar": h_tele, "qnh": q_val, "q_audio": ", ".join(list(q_val)),
            "temp": temp, "dew": dew, "w_dir_visu": w_dir_txt, "w_spd_visu": w_spd_txt,
            "w_audio_fr": w_audio_fr, "w_audio_en": w_audio_en
        }
    except: return None

def scanner_notams():
    resultats = {"R147": "Pas d'info"}
    try:
        res = requests.get("https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html"), timeout=15)
        texte = res.text.upper()
        if "R147" in texte:
            horaires = re.findall(r"R147.*?(\d{4}.*?TO.*?\d{4})", texte)
            resultats["R147"] = f"ACTIVE de {horaires[0].replace('TO', 'à')}" if horaires else "ACTIVE (voir NOTAM)"
    except: pass
    return resultats

async def generer_audio(vocal_fr, vocal_en):
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural").save("fr.mp3")
    await edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural").save("en.mp3")
    with open("atis.mp3", "wb") as f:
        for fname in ["fr.mp3", "en.mp3"]:
            with open(fname, "rb") as fd: f.write(fd.read())
    for f in ["fr.mp3", "en.mp3"]:
        if os.path.exists(f): os.remove(f)

async def executer_veille():
    m = obtenir_metar(ICAO)
    notams = scanner_notams()
    if not m: return

    # --- AUDIO ---
    txt_fr = (f"Atlantic Air Park. Observation de {m['heure_metar'].replace(':',' heures ')} UTC. "
              f"{m['w_audio_fr']}. Température {m['temp']} degrés. Point de rosée {m['dew']} degrés. "
              f"Q N H {m['q_audio']}. Piste en herbe zéro huit, deux six fermée. Prudence. Péril aviaire. "
              f"Zone R 147 : {notams['R147']}.")

    txt_en = (f"Atlantic Air Park. Observation at {m['heure_metar'].replace(':',' ')} UTC. "
              f"{m['w_audio_en']}. Temperature {m['temp']} degrees. Dew point {m['dew']} degrees. "
              f"Q N H {m['q_audio']}. Grass runway zero eight, two six, closed. Caution. Bird hazard. "
              f"Zone R 147 : {notams['R147']}.")

    await generer_audio(txt_fr, txt_en)

    # --- HTML ---
    remarques = ["Piste en herbe 08/26 fermée cause travaux", "Prudence", "Péril aviaire", f"RTBA R147 : {notams['R147']}"]
    alertes_html = "".join([f'<div class="alert-line">⚠️ {r}</div>' for r in remarques])

    html_content = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ATIS LF8523</title>
    <style>
        body {{ font-family: sans-serif; text-align: center; padding: 20px; background: #121212; color: #e0e0e0; }}
        .card {{ background: #1e1e1e; padding: 25px; border-radius: 15px; max-width: 500px; margin: auto; border: 1px solid #333; }}
        h1 {{ color: #fff; margin-bottom: 5px; }} .subtitle {{ color: #4dabff; font-weight: bold; margin-bottom: 25px; }}
        .data-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }}
        .data-item {{ background: #2a2a2a; padding: 15px; border-radius: 10px; border: 1px solid #3d3d3d; }}
        .label {{ font-size: 0.75em; color: #888; text-transform: uppercase; }}
        .value {{ font-size: 1.2em; font-weight: bold; color: #fff; margin-top:5px; }}
        .alert-section {{ text-align: left; background: rgba(255, 204, 0, 0.1); border-left: 4px solid #ffcc00; padding: 15px; margin-bottom: 25px; }}
        .alert-line {{ color: #ffcc00; font-weight: bold; font-size: 0.9em; margin-bottom: 8px; }}
        audio {{ width: 100%; filter: invert(90%); }}
    </style></head><body><div class="card">
    <h1>ATIS LF8523</h1><div class="subtitle">Atlantic Air Park</div>
    <div class="data-grid">
        <div class="data-item"><div class="label">Heure</div><div class="value">⌚ {m['heure_metar']}Z</div></div>
        <div class="data-item"><div class="label">Vent</div><div class="value">🌬 {m['w_dir_visu']} / {m['w_spd_visu']}kt</div></div>
        <div class="data-item"><div class="label">Temp / Rosée</div><div class="value">🌡 {m['temp']}° / {m['dew']}°</div></div>
        <div class="data-item"><div class="label">QNH</div><div class="value">💎 {m['qnh']} hPa</div></div>
    </div>
    <div class="alert-section">{alertes_html}</div>
    <div class="label" style="margin-bottom:10px;">Écouter l'audio</div>
    <audio controls autoplay><source src="atis.mp3" type="audio/mpeg"></audio>
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__":
    asyncio.run(executer_veille())
