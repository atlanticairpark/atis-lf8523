import requests
import os
import re

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def scanner_notams():
    zones_a_surveiller = ["R147", "R45A"]
    rapport = "📅 *PRÉVISIONS ZONES POUR DEMAIN*\n━━━━━━━━━━━━━━━━━━\n"
    alertes_trouvees = False
    
    try:
        # On interroge la FIR de Paris
        res = requests.get("https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html"), timeout=15)
        texte = res.text.upper()
        
        for zone in zones_a_surveiller:
            if zone in texte:
                # On cherche les horaires dans le NOTAM
                horaires = re.findall(rf"{zone}.*?(\d{{2}}\d{{2}}.*?TO.*?\d{{2}}\d{{2}})", texte)
                info = f"⚠️ *{zone}* : ACTIVE ({horaires[0] if horaires else 'Voir détails NOTAM'})"
                alertes_trouvees = True
            else:
                info = f"✅ *{zone}* : Aucune activation publiée"
            rapport += info + "\n"
            
    except Exception as e:
        rapport += "❌ Erreur lors de la lecture des NOTAM."

    if alertes_trouvees:
        rapport += "\nPrudence lors de votre navigation demain."
    
    return rapport

def envoyer_alerte():
    message = scanner_notams()
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})

if __name__ == "__main__":
    envoyer_alerte()
