import requests
import os
import re
import asyncio
import edge_tts
import time
import json
import glob
from datetime import datetime, timedelta, timezone

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
    q_str = str(m_q)
    q_audio_fr = " ".join([formater_chiffre_fr(c) for c in list(q_str)])
    if m_wd is None:
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

def scanner_notams(force_refresh=False):
    cache_file = "notam_cache.json"
    if not force_refresh and os.path.exists(cache_file):
        try:
            cache_age = datetime.now(timezone.utc).timestamp() - os.path.getmtime(cache_file)
            if cache_age < 300:  # 5 minutes max
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                    # Vérifier si la date du NOTAM est toujours valide
                    if cached["R147"]["date"]:
                        jour, mois = map(int, cached["R147"]["date"].split('/'))
                        annee = int(cached["R147"]["annee"])
                        date_notam = datetime(annee, mois, jour, tzinfo=timezone.utc)
                        if date_notam.date() >= datetime.now(timezone.utc).date():
                            print(f"DEBUG - Utilisation cache NOTAM (valide, age: {int(cache_age/60)} min)")
                            return cached
                        else:
                            print("DEBUG - Cache obsolète, rafraîchissement forcé")
                            os.remove(cache_file)
        except Exception as e:
            print(f"DEBUG - Erreur cache: {e}")

    print("DEBUG - Scan NOTAM en direct")
    status = {"R147": {"info": "pas d'information", "date": "", "annee": ""}}

    try:
        # 1. Essayer SIA
        url = "https://www.sia.aviation-civile.gouv.fr/schedules"
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            texte = res.text
            print(f"DEBUG - Texte brut SIA: {texte[:500]}...")
            match_r147 = re.search(
                r'(\d{2})/(\d{2})/(\d{4}).*?R\s*147.*?(?:(\d{1,2})[h:]?(\d{2})[^\d]*(?:à|to|-)[^\d]*(\d{1,2})[h:]?(\d{2}))',
                texte, re.IGNORECASE | re.DOTALL
            )
            if match_r147:
                jour, mois, annee = match_r147.group(1), match_r147.group(2), match_r147.group(3)
                h1, m1, h2, m2 = match_r147.group(4), match_r147.group(5), match_r147.group(6), match_r147.group(7)
                status["R147"]["date"] = f"{jour}/{mois}"
                status["R147"]["annee"] = annee
                status["R147"]["info"] = f"active {h1.zfill(2)}h{m1}-{h2.zfill(2)}h{m2}Z"
                print(f"DEBUG - Match R147: jour={jour}, mois={mois}, année={annee}")
                with open(cache_file, 'w') as f: json.dump(status, f)
                return status
            else:
                print("DEBUG - Aucun match R147 sur SIA")
    except Exception as e:
        print(f"Err SIA: {e}")

    # 2. Essayer NOTAMWEB
    try:
        url = "https://notamweb.aviation-civile.gouv.fr/Script/IHM/Bul_R.php?ZoneRglmt=RTBA"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        if res.status_code == 200:
            texte = res.text
            if 'R147' in texte or 'R 147' in texte:
                match = re.search(r'R\s*147.*?C(\d{10})/(\d{10})', texte, re.DOTALL | re.IGNORECASE)
                if match:
                    debut, fin = match.group(1), match.group(2)
                    status["R147"] = {
                        "date": f"{debut[4:6]}/{debut[2:4]}",
                        "annee": "20"+debut[0:2],
                        "info": f"active {debut[6:8]}:{debut[8:10]}-{fin[6:8]}:{fin[8:10]}Z"
                    }
                    print(f"DEBUG - Match NOTAMWEB: date={status['R147']['date']}, année={status['R147']['annee']}")
                else:
                    match_r147 = re.search(r'R147\s+CHARENTE\s+(\d{2})(\d{2})-(\d{2})(\d{2})', texte, re.IGNORECASE)
                    if match_r147:
                        pos_r147 = match_r147.start()
                        matches_date = list(re.finditer(r'DU:\s*(\d{2})\s+(\d{2})\s+(\d{4})', texte[:pos_r147], re.IGNORECASE))
                        if matches_date:
                            match_date = matches_date[-1]
                            h1, m1, h2, m2 = match_r147.group(1), match_r147.group(2), match_r147.group(3), match_r147.group(4)
                            status["R147"] = {
                                "date": f"{match_date.group(1)}/{match_date.group(2)}",
                                "annee": match_date.group(3),
                                "info": f"active {h1}:{m1}-{h2}:{m2}Z"
                            }
                            print(f"DEBUG - Match NOTAMWEB (fallback): date={status['R147']['date']}, année={status['R147']['annee']}")
                if status["R147"]["info"] != "pas d'information":
                    with open(cache_file, 'w') as f: json.dump(status, f)
                    return status
            else:
                print("DEBUG - R147 non trouvé sur NOTAMWEB")
    except Exception as e:
        print(f"Err NOTAMWEB: {e}")

    with open(cache_file, 'w') as f: json.dump(status, f)
    return status

async def generer_audio(vocal_fr, vocal_en):
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural", rate="+5%").save("fr.mp3")
    await edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural", rate="+10%").save("en.mp3")
    ts = int(time.time())
    with open(f"atis_{ts}.mp3", "wb") as f:
        for fname in ["fr.mp3", "en.mp3"]:
            with open(fname, "rb") as fd:
                f.write(fd.read())
    for old_file in glob.glob("atis_*.mp3"):
        if old_file != f"atis_{ts}.mp3":
            os.remove(old_file)
    os.rename(f"atis_{ts}.mp3", "atis.mp3")  # Remplace l'ancien fichier
    for f in ["fr.mp3", "en.mp3"]:
        if os.path.exists(f):
            os.remove(f)

async def executer_veille():
    m = obtenir_donnees_moyennes()
    force_refresh = os.getenv("FORCE_NOTAM_REFRESH", "0") == "1"
    notams = scanner_notams(force_refresh=force_refresh)
    if not m: return
    maintenant = datetime.now(timezone.utc)
    date_generation_courte = maintenant.strftime("%d/%m %H:%M")
    notam_r147_actif = False
    if notams['R147']['date'] and notams['R147']['annee']:
        try:
            jour, mois = notams['R147']['date'].split("/")
            date_notam = datetime(int(notams['R147']['annee']), int(mois), int(jour), tzinfo=timezone.utc)
            match_heure_fin = re.search(r'-(\d{2})h(\d{2})Z', notams['R147']['info'])
            if match_heure_fin:
                heure_fin = int(match_heure_fin.group(1))
                minute_fin = int(match_heure_fin.group(2))
                date_notam_fin = date_notam.replace(hour=heure_fin, minute=minute_fin)
                if date_notam.date() == maintenant.date():
                    notam_r147_actif = date_notam_fin > maintenant
                elif date_notam.date() > maintenant.date():
                    notam_r147_actif = True
            elif date_notam.date() >= maintenant.date():
                notam_r147_actif = True
        except: notam_r147_actif = "active" in notams['R147']['info'].lower()
    else: notam_r147_actif = "active" in notams['R147']['info'].lower()
    remarques_raw = os.getenv("ATIS_REMARQUES", "Piste en herbe 08/26 fermée :: Grass runway 08/26 closed")
    partie_fr, partie_en = remarques_raw.split("::") if "::" in remarques_raw else (remarques_raw, "Caution")
    liste_fr = [r.strip() for r in partie_fr.split("|")]
    liste_en = [r.strip() for r in partie_en.split("|")]
    html_remarques = "".join([f'<div class="alert-line">⚠️ {r}</div>' for r in liste_fr])
    audio_remarques_fr = ". ".join(liste_fr) + "."
    audio_remarques_en = ". ".join(liste_en) + "."
    notam_audio_fr = ""
    if notam_r147_actif:
        match_h = re.search(r'active (\d{2})h(\d{2})-(\d{2})h(\d{2})Z', notams['R147']['info'])
        if match_h:
            h1,m1,h2,m2 = match_h.groups()
            notam_audio_fr = f"Zone R 147 : active le {notams['R147']['date']} de {int(h1)} heures{(' '+str(int(m1))) if int(m1)>0 else ''} à {int(h2)} heures{(' '+str(int(m2))) if int(m2)>0 else ''} UTC."
    txt_fr = f"Atlantic Air Park, observation de {m['heure_metar'].replace(':',' heures ')} UTC. {m['w_audio_fr']}. Température {m['t_audio_fr']} degrés. Point de rosée {m['d_audio_fr']} degrés. Q N H {m['q_audio_fr']} hectopascals. {audio_remarques_fr} {notam_audio_fr}"
    notam_audio_en = ""
    if notam_r147_actif:
        match_h = re.search(r'active (\d{2})h(\d{2})-(\d{2})h(\d{2})Z', notams['R147']['info'])
        if match_h:
            h1,m1,h2,m2 = match_h.groups()
            notam_audio_en = f"Military zone R 147: active on {notams['R147']['date'].replace('/',' ')} from {int(h1)}{(' '+str(int(m1))) if int(m1)>0 else ''} to {int(h2)}{(' '+str(int(m2))) if int(m2)>0 else ''} UTC."
    txt_en = f"Atlantic Air Park observation at {m['heure_metar'].replace(':',' ')} UTC. {m['w_audio_en']}. Temperature {m['t_audio_en']} degrees. Dew point {m['d_audio_en']} degrees. Q N H {m['q_audio_en']} hectopascals. {audio_remarques_en} {notam_audio_en}"
    await generer_audio(txt_fr, txt_en)
    ts = int(time.time())
    prochaine = (maintenant.replace(minute=0,second=0) + timedelta(hours=1)).strftime('%H:%M')
    html = f"""<!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
        <meta http-equiv="Pragma" content="no-cache">
        <meta http-equiv="Expires" content="0">
        <title>ATIS LF8523</title>
        <style>
            *{{box-sizing:border-box}}body{{font-family:-apple-system,sans-serif;padding:2.5vh 2.5vw;background:linear-gradient(135deg,#2c5f7c,#4a90b8,#6bb6d6);color:#e0e0e0;min-height:100vh;margin:0}}.container{{width:95%;margin:0 auto}}h1{{color:#fff;margin:0 0 8px 0;font-size:2em;font-weight:700;text-align:center}}.subtitle{{color:#fff;font-weight:600;margin-bottom:30px;text-transform:uppercase;letter-spacing:2px;font-size:.85em;text-align:center;opacity:.9}}.data-grid{{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:25px}}.data-item{{background:rgba(20,60,90,.6);padding:18px;border-radius:12px;border:1px solid rgba(100,180,220,.3);transition:all .3s;backdrop-filter:blur(5px)}}.data-item:hover{{background:rgba(20,60,90,.75);transform:translateY(-2px)}}.label{{font-size:.7em;color:rgba(255,255,255,.7);text-transform:uppercase;font-weight:600}}.value{{font-size:1.3em;font-weight:700;color:#fff;margin-top:8px}}.alert-section{{text-align:left;background:rgba(20,60,90,.5);border-left:4px solid #ff9800;padding:18px;margin-bottom:25px;border-radius:8px}}.alert-line{{color:#ffb74d;font-weight:600;font-size:.9em;margin-bottom:10px}}.zone-date{{display:inline-block;background:rgba(255,183,77,.25);padding:3px 10px;border-radius:6px;margin-left:8px;color:#ffd54f;font-weight:700;border:1px solid rgba(255,183,77,.4)}}.audio-container{{background:rgba(20,60,90,.6);padding:15px;border-radius:12px;margin:20px 0;border:2px solid rgba(100,180,220,.4)}}.audio-label{{font-size:.85em;color:#fff;font-weight:700;text-transform:uppercase;margin-bottom:10px;display:block}}audio{{width:100%;filter:invert(90%) hue-rotate(180deg);border-radius:8px;height:40px}}.btn-refresh{{background:rgba(20,60,90,.7);color:#fff;border:2px solid rgba(100,180,220,.5);padding:14px 24px;border-radius:10px;cursor:pointer;margin-top:20px;font-size:.95em;font-weight:700;width:100%;text-transform:uppercase}}.btn-refresh:hover{{background:rgba(20,60,90,.85);transform:translateY(-2px)}}.update-info{{font-size:.9em;color:#fff;margin-top:12px;font-weight:600;background:rgba(20,60,90,.5);padding:8px 12px;border-radius:8px;text-align:center}}.disclaimer{{font-size:.7em;color:rgba(255,255,255,.8);margin-top:30px;line-height:1.6;text-align:left;background:rgba(20,60,90,.4);padding:15px;border-radius:8px;border-left:3px solid #ff9800}}.disclaimer strong{{color:#fff;font-weight:700}}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>ATIS LF8523</h1>
            <div class="subtitle">Atlantic Air Park</div>
            <div class="data-grid">
                <div class="data-item">
                    <div class="label">Heure (UTC)</div>
                    <div class="value">⌚ {m['heure_metar']}Z</div>
                </div>
                <div class="data-item">
                    <div class="label">Vent</div>
                    <div class="value">🌬 {m['w_dir_visu']}kt</div>
                </div>
                <div class="data-item">
                    <div class="label">Temp / Rosée</div>
                    <div class="value">🌡 {m['temp_visu']}° / {m['dew_visu']}°</div>
                </div>
                <div class="data-item">
                    <div class="label">QNH</div>
                    <div class="value">💎 {m['qnh']} hPa</div>
                </div>
            </div>
            <div class="alert-section">
                {html_remarques}
                {('<div class="alert-line">🚨 R147 CHARENTE : '+notams["R147"]["info"]+('<span class="zone-date">📅 '+notams["R147"]["date"]+'</span>' if notams["R147"]["date"] else '')+'</div>') if notam_r147_actif else ''}
            </div>
            <div class="audio-container">
                <span class="audio-label">🔊 Écouter l'ATIS</span>
                <audio controls>
                    <source src="atis.mp3?v={ts}" type="audio/mpeg">
                </audio>
            </div>
            <button id="force-refresh" class="btn-refresh">🔄 Actualiser les données</button>
            <div class="update-info">🕐 Données: {date_generation_courte}</div>
            <div style="font-size:.75em;color:rgba(255,255,255,.6);margin-top:8px;text-align:center">ℹ️ Prochaine mise à jour: {prochaine}Z</div>
            <div class="disclaimer">
                <strong>⚠️ Avertissement:</strong> Les informations affichées sont indicatives et calculées à partir de sources publiques (moyennes LFBH/LFRI). <strong>Atlantic Air Park ne garantit pas l'exactitude de ces données.</strong> Seules les informations officielles publiées par les autorités aéronautiques compétentes (SIA, Météo France, etc.) font foi. Il est impératif de consulter les sources officielles avant tout vol.
            </div>
        </div>
        <script>
            document.getElementById('force-refresh').addEventListener('click', function() {{
                window.location.href = window.location.href.split('?')[0] + '?t=' + new Date().getTime();
            }});
        </script>
    </body>
    </html>"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    asyncio.run(executer_veille())
