import requests
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def recuperer_meteo(icao):
    # Utilisation d'une API météo aéronautique gratuite (avwx par exemple)
    url = f"https://avwx.rest/api/metar/{icao}?format=json"
    try:
        response = requests.get(url)
        return response.json()
    except:
        return None

def calculer_moyenne_atlantique():
    m1 = recuperer_meteo("LFBH") # La Rochelle
    m2 = recuperer_meteo("LFRI") # La Roche-sur-Yon
    
    if m1 and m2:
        # Calcul des moyennes
        qnh = (m1['altimeter']['value'] + m2['altimeter']['value']) / 2
        temp = (m1['temperature']['value'] + m2['temperature']['value']) / 2
        dew = (m1['dewpoint']['value'] + m2['dewpoint']['value']) / 2
        
        # Pour le vent, on prend souvent la valeur la plus prudente ou la moyenne
        v_vitesse = (m1['wind_speed']['value'] + m2['wind_speed']['value']) / 2
        
        msg = (
            f"🌡 *ESTIMATION MÉTÉO LF038*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 *Moyenne LFBH / LFRI*\n"
            f"🔹 *QNH :* {qnh:.0f} hPa\n"
            f"🔹 *Vent :* {v_vitesse:.0s} kt\n"
            f"🔹 *OAT :* {temp:.1f}°C\n"
            f"🔹 *Point de rosée :* {dew:.1f}°C\n"
        )
        return msg
    return "Erreur récupération météo."

# ... (garder ta fonction verifier_r147 ici) ...
