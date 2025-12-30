import requests
import os
import re
import asyncio
import edge_tts
import time

# Configuration
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
                w_match = re.search(r' (\d{3})(\d{2})(G\d{2})?KT', metar)
                if w_match:
                    vents_dir.append(int(w_match.group(1)))
                    vents_spd.append(int(w_match.group(2)))
                    if w_match.group(3): rafales.append(int(w_match.group(3).replace('G', '')))
        except: continue

    if not qnhs: return None
    m_t, m_r, m_q = round(sum(temps)/len(temps)), round(sum(rosees)/len(rosees)), round(sum(qnhs)/len(qnhs))
    m_wd, m_ws = round(sum(vents_dir)/len(vents_dir)), round(sum(vents_spd)/len(vents_spd))
    max_g = max(rafales) if rafales else None
    q_str = str(m_q)
    q_audio_fr = " ".join([formater_chiffre_fr(c) for c in list(q_str)])
    wd_en = " ".join(list(str(m_wd).zfill(3))).replace('0','zero').replace('1','one')
    v_fr, v_en = f"vent {m_wd} degrés, {m_ws} nœuds", f"wind {wd_en} degrees, {m_ws} knots"
    v_visu = f"{str(m_wd).zfill(3)} / {m_ws}"
    if max_g and max_g > m_ws:
        v_fr += f", avec rafales à {max_g} nœuds"; v_en += f", gusting {max_g} knots"; v_visu += f"G{max_g}"

    return {
        "heure_metar": h_tele, "qnh": q_str, "q_audio_fr": q_audio_fr, "q_audio_en": " ".join(list(q_str)),
        "temp_visu": str(m_t), "dew_visu": str(m_r),
        "t_audio_fr": (("moins " if m_t < 0 else "") + formater_chiffre_fr(abs(m_t))),
        "d_audio_fr": (("moins " if m_r < 0 else "") + formater_chiffre_fr(abs(m_r))),
        "t_audio_en": (("minus " if m_t < 0 else "") + str(abs(m_t))),
        "d_audio_en": (("minus " if m_r < 0 else "") + str(abs(m_r))),
        "w_dir_visu": v_visu, "w_audio_fr": v_fr, "w_audio_en": v_en
    }

def scanner_notams():
    status = {"R147": "pas d'information", "R45A": "pas d'information"}
    try:
        res = requests.get("https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html"), timeout=15)
        texte = res.text.upper()
        for zone in ["R147", "R45A"]:
            match = re.search(f"{zone}.*?(\\d{{4}}.*?TO.*?\\d{{4}})", texte)
            if match:
                status[zone] = f"active de {match.group(1).replace('TO', 'à')}"
    except: pass
    return status

async def generer_audio(vocal_fr, vocal_en):
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural", rate="+5%").save("fr.mp3")
    await edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural", rate="+10%").save("en.mp3")
    with open("atis.mp3", "wb") as f:
        for fname in ["fr.mp3", "en.mp3"]:
            with open(fname, "rb") as fd: f.write(fd.read())
    for f in ["fr.mp3", "en.mp3"]:
        if os.path.exists(f): os.remove(f)

async def executer_veille():
    m = obtenir_donnees_moyennes()
    notams = scanner_notams()
    if not m: return

    # RÉCUPÉRATION DES REMARQUES DEPUIS GITHUB
    remarques_raw = os.getenv("ATIS_REMARQUES", "Piste en herbe 08/26 fermée cause travaux | Prudence / Péril aviaire")
    liste_remarques = [r.strip() for r in remarques_raw.split("|")]
    
    html_remarques = "".join([f'<div class="alert-line">⚠️ {r}</div>' for r in liste_remarques])
    audio_remarques = ". ".join(liste_remarques) + "."

    # AUDIO
    notam_audio = f"Zone R 147 : {notams['R147']}."
    if "active" in notams['R45A']:
        notam_audio += f" Notez également zone R 45 alpha {notams['R45A']}."

    txt_fr = (f"Atlantic Air Park, observation de {m['heure_metar'].replace(':',' heures ')} UTC. "
              f"{m['w_audio_fr']}. Température {m['t_audio_fr']} degrés. Point de rosée {m['d_audio_fr']} degrés. "
              f"Q N H {m['q_audio_fr']} hectopascals. "
              f"{audio_remarques} "
              f"{notam_audio}")

    txt_en = (f"Atlantic Air Park observation at {m['heure_metar'].replace(':',' ')} UTC. "
              f"{m['w_audio_en']}. Temperature {m['t_audio_en']} degrees. Dew point {m['d_audio_en']} degrees. "
              f"Q N H {m['q_audio_en']} hectopascals. Caution. Bird hazard. "
              f"Check NOTAM for military areas.")

    await generer_audio(txt_fr, txt_en)

    ts = int(time.time())
    html_content = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ATIS LF8523</title>
    <style>
        body {{ font-family: sans-serif; text-align: center; padding: 20px; background: #121212; color: #e0e0e0; }}
        .card {{ background: #1e1e1e; padding: 25px; border-radius: 15px; max-width: 500px; margin: auto; border: 1px solid #333; }}
        h1 {{ color: #fff; margin-bottom: 5px; }} .subtitle {{ color: #4dabff; font-weight: bold; margin-bottom: 25px; text-transform: uppercase; }}
        .data-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }}
        .data-item {{ background: #2a2a2a; padding: 15px; border-radius: 10px; border: 1px solid #3d3d3d; }}
        .label {{ font-size: 0.75em; color: #888; text-transform: uppercase; }}
        .value {{ font-size: 1.2em; font-weight: bold; color: #fff; margin-top:5px; }}
        .alert-section {{ text-align: left; background: rgba(255, 204, 0, 0.1); border-left: 4px solid #ffcc00; padding: 15px; margin-bottom: 25px; }}
        .alert-line {{ color: #ffcc00; font-weight: bold; font-size: 0.9em; margin-bottom: 8px; }}
        audio {{ width: 100%; filter: invert(90%); margin-top: 10px; }}
        .btn-refresh {{ background: #333; color: #ccc; border: 1px solid #444; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-top: 20px; font-size: 0.85em; transition: 0.3s; font-weight: bold; }}
        .btn-refresh:hover {{ background: #444; color: #fff; border-color: #666; }}
        .disclaimer {{ font-size: 0.7em; color: #ccc; margin-top: 30px; line-height: 1.4; font-style: italic; border-top: 1px solid #333; padding-top: 15px; text-align: justify; }}
    </style></head><body><div class="card">
    <h1>ATIS LF8523</h1><div class="subtitle">Atlantic Air Park</div>
    <div class="data-grid">
        <div class="data-item"><div class="label">Heure (UTC)</div><div class="value">⌚ {m['heure_metar']}Z</div></div>
        <div class="data-item"><div class="label">Vent</div><div class="value">🌬 {m['w_dir_visu']}kt</div></div>
        <div class="data-item"><div class="label">Temp / Rosée</div><div class="value">🌡 {m['temp_visu']}° / {m['dew_visu']}°</div></div>
        <div class="data-item"><div class="label">QNH</div><div class="value">💎 {m['qnh']} hPa</div></div>
    </div>
    <div class="alert-section">
        {html_remarques}
        <div class="alert-line">⚠️ RTBA R147 : {notams['R147']}</div>
        <div class="alert-line" style="color:#4dabff; font-size: 0.8em;">🔹 TEST R45A : {notams['R45A']}</div>
    </div>
    <div class="label" style="margin-bottom:10px;">Écouter l'audio (Bilingue)</div>
    <audio controls><source src="atis.mp3?v={ts}" type="audio/mpeg"></audio>
    <br><button class="btn-refresh" onclick="window.location.replace(window.location.pathname + '?refresh=' + Date.now())">🔄 Actualiser les données</button>
    <div class="disclaimer">
        Valeurs issues des METAR LFBH (La Rochelle) et LFRI (La Roche-sur-Yon) moyennées. Les rafales correspondent à la valeur maximale observée.<br><br>
        Ce service est une aide à l'information. Atlantic Air Park ne saurait être tenu responsable en cas d'erreur ou d'omission. Seule la documentation officielle (SIA/Météo-France) fait foi.
    </div>
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__":
    asyncio.run(executer_veille())
