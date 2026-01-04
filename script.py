import requests
import os
import re
import asyncio
import edge_tts
import time

# =================================================================
# MODE D'EMPLOI DU SECRET "ATIS_REMARQUES" SUR GITHUB :
# Format : Ligne FR 1 | Ligne FR 2 :: Line EN 1 | Line EN 2
# Le "::" sépare le Français de l'Anglais.
# Le "|" sépare les lignes (sauts de ligne).
# =================================================================

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
                
                # Heure
                time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
                if time_match: h_tele = f"{time_match.group(2)}:{time_match.group(3)}"
                
                # Température / Rosée
                tr_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
                if tr_match:
                    temps.append(int(tr_match.group(1).replace('M', '-')))
                    rosees.append(int(tr_match.group(2).replace('M', '-')))
                
                # QNH
                q_match = re.search(r'Q(\d{4})', metar)
                if q_match: qnhs.append(int(q_match.group(1)))
                
                # VENT (Support VRB, directions fixes et rafales G)
                w_match = re.search(r' ([0-9]{3}|VRB)(\d{2})(G\d{2})?KT', metar)
                if w_match:
                    direction = w_match.group(1)
                    vitesse = int(w_match.group(2))
                    if direction != "VRB":
                        vents_dir.append(int(direction))
                    vents_spd.append(vitesse)
                    if w_match.group(3):
                        rafales.append(int(w_match.group(3).replace('G', '')))
        except: continue

    if not vents_spd or not qnhs: return None

    m_t = round(sum(temps)/len(temps)) if temps else 0
    m_r = round(sum(rosees)/len(rosees)) if rosees else 0
    m_q = round(sum(qnhs)/len(qnhs))
    m_wd = round(sum(vents_dir)/len(vents_dir)) if vents_dir else None
    m_ws = round(sum(vents_spd)/len(vents_spd))
    max_g = max(rafales) if rafales else None

    q_str = str(m_q)
    q_audio_fr = " ".join([formater_chiffre_fr(c) for c in list(q_str)])
    
    # Formatage Vent
    if m_wd is None: # Cas VRB
        v_fr, v_en = f"vent variable, {m_ws} nœuds", f"wind variable, {m_ws} knots"
        v_visu = f"VRB / {m_ws}"
    else:
        wd_str = str(m_wd).zfill(3)
        wd_en = " ".join(list(wd_str)).replace('0','zero').replace('1','one')
        v_fr, v_en = f"vent {m_wd} degrés, {m_ws} nœuds", f"wind {wd_en} degrees, {m_ws} knots"
        v_visu = f"{wd_str} / {m_ws}"

    if max_g and max_g > m_ws:
        v_fr += f", avec rafales à {max_g} nœuds"
        v_en += f", gusting {max_g} knots"
        v_visu += f"G{max_g}"

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
        # On interroge la source (LFRR pour l'Ouest, mais le flux contient souvent les RTBA nationales)
        res = requests.get("https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html"), timeout=15)
        # On remplace les sauts de ligne par des espaces pour que la regex ne bloque pas
        texte = res.text.upper().replace('\n', ' ').replace('\r', ' ')
        
        for zone in ["R147", "R45A"]:
            # Cette regex cherche le nom de la zone, puis ignore le texte jusqu'à trouver 
            # un format type 1430-1600:ACTIVE
            match = re.search(rf"{zone}.*?(\d{{4}}-\d{{4}}:ACTIVE)", texte)
            
            if match:
                # On extrait "1430-1600:ACTIVE" et on le rend plus lisible
                info = match.group(1).replace(':ACTIVE', '').replace('-', ' à ')
                # On ajoute un formattage pour que ce soit propre (ex: 14:30 à 16:00)
                h_debut = info[:2] + ":" + info[2:4]
                h_fin = info[-5:-3] + ":" + info[-2:]
                status[zone] = f"active de {h_debut} à {h_fin}"
            elif zone in texte:
                # Sécurité : si la zone est citée mais que le format horaire diffère
                status[zone] = "citée dans un NOTAM (vérifier SIA)"
    except:
        pass
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

    remarques_raw = os.getenv("ATIS_REMARQUES", "Piste en herbe 08/26 fermée cause travaux | Prudence :: Grass runway 08/26 closed due to works | Caution")
    partie_fr, partie_en = remarques_raw.split("::") if "::" in remarques_raw else (remarques_raw, "Caution")
    
    liste_fr = [r.strip() for r in partie_fr.split("|")]
    liste_en = [r.strip() for r in partie_en.split("|")]
    
    html_remarques = "".join([f'<div class="alert-line">⚠️ {r}</div>' for r in liste_fr])
    audio_remarques_fr = ". ".join(liste_fr) + "."
    audio_remarques_en = ". ".join(liste_en) + "."

    # AUDIO FR
    notam_audio_fr = f"Zone R 147 : {notams['R147']}."
    if "active" in notams['R45A']: notam_audio_fr += f" Notez également zone R 45 alpha {notams['R45A']}."

    txt_fr = (f"Atlantic Air Park, observation de {m['heure_metar'].replace(':',' heures ')} UTC. "
              f"{m['w_audio_fr']}. Température {m['t_audio_fr']} degrés. Point de rosée {m['d_audio_fr']} degrés. "
              f"Q N H {m['q_audio_fr']} hectopascals. {audio_remarques_fr} {notam_audio_fr}")

    # AUDIO EN
    txt_en = (f"Atlantic Air Park observation at {m['heure_metar'].replace(':',' ')} UTC. "
              f"{m['w_audio_en']}. Temperature {m['t_audio_en']} degrees. Dew point {m['d_audio_en']} degrees. "
              f"Q N H {m['q_audio_en']} hectopascals. {audio_remarques_en} Check NOTAM for military areas.")

    await generer_audio(txt_fr, txt_en)
    ts = int(time.time())

    html_content = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ATIS LF8523</title>
    <link rel="manifest" href="manifest.json?v=2">
    <link rel="apple-touch-icon" href="icon.png?v=2">
    <link rel="icon" type="image/png" href="icon.png?v=2">
    <style>
        body {{ font-family: sans-serif; text-align: center; padding: 20px; background: #121212; color: #e0e0e0; min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .card {{ background: #1e1e1e; padding: 25px; border-radius: 15px; max-width: 500px; width: 90%; border: 1px solid #333; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
        h1 {{ color: #fff; margin: 0 0 5px 0; font-size: 1.8em; }} 
        .subtitle {{ color: #4dabff; font-weight: bold; margin-bottom: 25px; text-transform: uppercase; letter-spacing: 1px; font-size: 0.9em; }}
        .data-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }}
        .data-item {{ background: #2a2a2a; padding: 15px; border-radius: 10px; border: 1px solid #3d3d3d; }}
        .label {{ font-size: 0.75em; color: #888; text-transform: uppercase; }}
        .value {{ font-size: 1.2em; font-weight: bold; color: #fff; margin-top:5px; }}
        .alert-section {{ text-align: left; background: rgba(255, 204, 0, 0.1); border-left: 4px solid #ffcc00; padding: 15px; margin-bottom: 25px; }}
        .alert-line {{ color: #ffcc00; font-weight: bold; font-size: 0.9em; margin-bottom: 8px; }}
        audio {{ width: 100%; filter: invert(90%); margin-top: 10px; }}
        .btn-refresh {{ background: #333; color: #ccc; border: 1px solid #444; padding: 12px 20px; border-radius: 8px; cursor: pointer; margin-top: 20px; font-size: 0.9em; transition: 0.3s; font-weight: bold; width: 100%; }}
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
        <div class="alert-line" style="color:#4dabff; font-size: 0.85em;">🔹 TEST R45A : {notams['R45A']}</div>
    </div>
    <audio controls><source src="atis.mp3?v={ts}" type="audio/mpeg"></audio>
    <button class="btn-refresh" onclick="window.location.reload()">🔄 Actualiser les données</button>
    <div class="disclaimer">Valeurs issues des moyennes LFBH/LFRI. Seule la doc officielle fait foi.</div>
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__":
    asyncio.run(executer_veille())
