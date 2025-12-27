import requests
import os

# Secrets GitHub
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- CONFIGURATION MANUELLE DES INFOS TERRAIN ---
# Modifie ces textes entre les guillemets selon les besoins du moment
INFOS_LOCALES = "Piste en herbe fermée (terrain gras). Péril aviaire signalé en bout de piste 24."

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def obtenir_metar(icao):
    # Source gratuite pour les METAR
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url)
        line = response.text.split('\n')[1]
        # Extraction simplifiée du QNH (ex: Q1018)
        qnh = int(line.split('Q')[1][:4])
        # Extraction Température/Point rosée (ex: 12/08)
        temp_part = line.split(' ')[-3]
        temp = int(temp_part.split('/')[0].replace('M', '-'))
        dew = int(temp_part.split('/')[1].replace('M', '-'))
        return {"qnh": qnh, "temp": temp, "dew": dew}
    except:
        return None

def executer_veille():
    rapport = "📡 *BULLETIN AUTOMATIQUE LF038*\n━━━━━━━━━━━━━━━━━━\n\n"
    
    # 1. MÉTÉO MOYENNÉE
    m_lfbh = obtenir_metar("LFBH")
    m_lfri = obtenir_metar("LFRI")
    
    if m_lfbh and m_lfri:
        qnh_moy = (m_lfbh['qnh'] + m_lfri['qnh']) / 2
        temp_moy = (m_lfbh['temp'] + m_lfri['temp']) / 2
        dew_moy = (m_lfbh['dew'] + m_lfri['dew']) / 2
        rapport += f"🌤 *Météo (Moyenne LFBH/LFRI) :*\n• QNH : {qnh_moy:.0f} hPa\n• Temp : {temp_moy:.1f}°C\n• Rosée : {dew_moy:.1f}°C\n\n"
    
    # 2. INFOS TERRAIN (Tes messages)
    rapport += f"⚠️ *Infos Atlantic Air Park :*\n{INFOS_LOCALES}\n\n"
    
    # 3. SURVEILLANCE R147
    url_notam = "https://api.aviation-edge.com/api/public/notam?region=LFRR"
    try:
        res = requests.get(url_notam)
        notams = res.json()
        r147_detectee = False
        for n in notams:
            if "R147" in str(n).upper():
                r147_detectee = True
                rapport += f"🚫 *ZONE R147 ACTIVE !*\nConsultez le détail sur le SIA.\n"
                break
        if not r147_detectee:
            rapport += "✅ Zone R147 non signalée active.\n"
    except:
        rapport += "❌ Erreur scan NOTAM.\n"

    envoyer_telegram(rapport)

if __name__ == "__main__":
    executer_veille()
