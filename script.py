import requests
import os

# Récupération des clés sécurisées depuis GitHub Actions
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
# Utilisation de l'API de OpenAviationData (très fiable pour la zone France)
URL_API = "https://api.aviation-donnees.fr/v1/notams/LFRR"

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def verifier_notam():
    try:
        response = requests.get(URL_API)
        notams = response.json()
        
        for n in notams:
            texte = n.get('text', '').upper()
            
            # Filtrage spécifique sur la R147
            if "R147" in texte or "R 147" in texte:
                msg = (
                    f"📢 *ALERTE ZONE R147*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🗓 *Début :* {n.get('start_date')}\n"
                    f"🏁 *Fin :* {n.get('end_date')}\n"
                    f"📝 *Info :* {texte[:200]}..." # On coupe si c'est trop long
                )
                envoyer_telegram(msg)
                
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    verifier_notam()
