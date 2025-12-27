import requests
import os
import re

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- CONFIGURATION MANUELLE LF8523 ---
INFOS_LOCALES = "Piste 08/26 : Piste en herbe FERMÉE cause travaux. Prudence péril aviaire."

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return None
        metar = response.text.split('\n')[1]
        
        # Vent
        wind_match = re.search(r' (\d{3})(\d{2})KT', metar)
        w_dir = int(wind_match.group(1)) if wind_match else None
        w_spd = int(wind_match.group(2)) if wind_match else None
        
        # QNH
        qnh_match = re.search(r'Q(\d{4})', metar)
        qnh = int(qnh_match.group(1)) if qnh_match else None
        
        # Temp/Dew
        temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        t = int(temp_match.group(1).replace('M', '-')) if temp_match else None
        d = int(temp_match.group(2).replace('M', '-')) if temp_match else None
            
        return {"qnh": qnh, "temp": t, "dew": d, "wind_dir": w_dir, "wind_speed": w_spd}
    except:
        return None

def executer_veille():
    rapport = f"🛩 *BULLETIN AUTOMATIQUE LF8523*\n(Atlantic Air Park)\n━━━━━━━━━━━━━━━━━━\n\n"
    
    # 1. MÉTEO
    m1, m2 = obtenir_metar("LFBH"), obtenir_metar("LFRI")
    if m1 and m2:
        q_moy = (m1['qnh'] + m2['qnh']) / 2
        t_moy = (m1['temp'] + m2['temp']) / 2
        d_moy = (m1['dew'] + m2['dew']) / 2
        if m1['wind_dir'] is not None:
            wd = (m1['wind_dir'] + m2['wind_dir']) / 2
            ws = (m1['wind_speed'] + m2['wind_speed']) / 2
            rapport += f"🌤 *Météo (Moyenne LFBH/LFRI) :*\n• Vent : {wd:03.0f}° / {ws:.0f} kt\n• QNH : {q_moy:.0f} hPa\n• Temp : {t_moy:.1f}°C\n• Rosée : {d_moy:.1f}°C\n\n"
    
    # 2. INFOS TERRAIN
    rapport += f"🚧 *Infos Terrain :*\n{INFOS_LOCALES}\n\n"
    
    # 3. NOTAM R147 (Méthode de scan direct par mot-clé)
    # On utilise un service de consultation public simple
    r147_status = "✅ Non signalée"
    try:
        # On va chercher la page des NOTAM de la FIR de Paris (LFRR)
        url_notam = "https://www.notams.faa.gov/common/icao/LFRR.html"
        headers = {'User-Agent': 'Mozilla/5.0'} # On fait croire qu'on est un navigateur web
        res = requests.get(url_notam, headers=headers, timeout=15)
        
        if res.status_code == 200:
            if "R147" in res.text.upper():
                r147_status = "⚠️ ACTIVÉE (Voir SIA/Sofia)"
        else:
            r147_status = "❓ Serveur NOTAM occupé"
    except:
        r147_status = "❓ Vérification manuelle (SIA)"

    rapport += f"🚫 *Zone R147 :* {r147_status}\n"
    rapport += "\n_Généré par le système Atlantic Air Park._"
    
    envoyer_telegram(rapport)

if __name__ == "__main__":
    executer_veille()
