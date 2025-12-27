import requests
import os
import re

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

INFOS_LOCALES = "Piste 08/26 : Piste en herbe FERMÉE cause travaux. Prudence péril aviaire."

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def obtenir_metar(icao):
    # On utilise une autre URL NOAA au cas où
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        metar = response.text.split('\n')[1]
        w_match = re.search(r' (\d{3})(\d{2})KT', metar)
        q_match = re.search(r'Q(\d{4})', metar)
        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        
        return {
            "qnh": int(q_match.group(1)) if q_match else None,
            "temp": int(t_match.group(1).replace('M', '-')) if t_match else None,
            "dew": int(t_match.group(2).replace('M', '-')) if t_match else None,
            "w_dir": int(w_match.group(1)) if w_match else None,
            "w_spd": int(w_match.group(2)) if w_match else None
        }
    except: return None

def executer_veille():
    rapport = f"🛩 *BULLETIN AUTOMATIQUE LF8523*\n(Atlantic Air Park)\n━━━━━━━━━━━━━━━━━━\n\n"
    
    m1, m2 = obtenir_metar("LFBH"), obtenir_metar("LFRI")
    if m1 and m2:
        q_moy = (m1['qnh'] + m2['qnh']) / 2
        t_moy = (m1['temp'] + m2['temp']) / 2
        d_moy = (m1['dew'] + m2['dew']) / 2
        wd = (m1['w_dir'] + m2['w_dir']) / 2
        ws = (m1['w_spd'] + m2['w_spd']) / 2
        rapport += f"🌤 *Météo (Moyenne LFBH/LFRI) :*\n• Vent : {wd:03.0f}° / {ws:.0f} kt\n• QNH : {q_moy:.0f} hPa\n• Temp : {t_moy:.1f}°C\n• Rosée : {d_moy:.1f}°C\n\n"

    rapport += f"🚧 *Infos Terrain :*\n{INFOS_LOCALES}\n\n"

    # --- TENTATIVE NOTAM SOURCE ALTERNATIVE ---
    r147_status = "✅ Non signalée"
    try:
        # Source 1 : API de secours simplifiée
        check_url = "https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html")
        res = requests.get(check_url, timeout=15)
        if "R147" in res.text.upper():
            r147_status = "⚠️ ACTIVÉE (Vérifiez SIA/Sofia)"
    except:
        r147_status = "❓ Vérification manuelle (SIA)"

    rapport += f"🚫 *Zone R147 :* {r147_status}\n"
    rapport += "\n_Généré par le système Atlantic Air Park._"
    envoyer_telegram(rapport)

if __name__ == "__main__":
    executer_veille()
