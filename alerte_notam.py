import requests
import os
import re
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def scanner_notams():
    """
    Scanne les NOTAM pour R147 en cherchant spécifiquement la date de demain.
    """
    demain_dt = datetime.now() + timedelta(days=1)
    demain_str = demain_dt.strftime("%d/%m/%Y")
    
    status = {
        "R147": {"info": "pas d'information", "date": "", "annee": ""}
    }
    
    try:
        url = "https://www.sia.aviation-civile.gouv.fr/schedules"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            texte = res.text
            
            # Recherche précise : Date de demain + R147 + Horaires
            # On utilise le format de date JJ/MM/AAAA tel qu'affiché sur le SIA
            pattern = rf'({demain_str}).*?R\s*147.*?(\d{{2}}):?(\d{{2}})[^\d]*(\d{{2}}):?(\d{{2}})'
            match_r147 = re.search(pattern, texte, re.IGNORECASE | re.DOTALL)
            
            if match_r147:
                status["R147"] = {
                    "date": f"{match_r147.group(1)}", # Date complète
                    "info": f"active {match_r147.group(2)}h{match_r147.group(3)}-{match_r147.group(4)}h{match_r147.group(5)}Z"
                }
    except Exception as e:
        print(f"Erreur lors du scan : {e}")
            
    return status

def construire_message():
    """
    Construit le rapport pour Telegram.
    Retourne None si aucune activation n'est trouvée.
    """
    notams = scanner_notams()
    maintenant = datetime.now()
    demain = maintenant + timedelta(days=1)
    demain_str = demain.strftime("%d/%m/%Y")
    
    # Si pas d'info ou pas d'activation pour demain, on retourne None
    if notams["R147"]["info"] == "pas d'information":
        return None

    rapport = f"📅 *PRÉVISIONS ZONE R147 POUR DEMAIN ({demain_str})*\n"
    rapport += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    info = notams["R147"]["info"]
    rapport += "⚠️ *R147 CHARENTE*\n"
    rapport += f"🔴 **{info.upper()}**\n\n"
    rapport += "📋 *Vérifiez les NOTAM officiels :*\n"
    rapport += "• https://notamweb.aviation-civile.gouv.fr\n"
    rapport += "• https://www.sia.aviation-civile.gouv.fr\n\n"
    rapport += "⚠️ Ne présumez JAMAIS qu'une zone est inactive sans vérification officielle.\n"
    rapport += f"\n🕐 Mise à jour : {maintenant.strftime('%d/%m/%Y %H:%M')}"
    
    return rapport

def envoyer_alerte():
    """
    Envoie le message sur Telegram uniquement s'il y a une activation.
    """
    if not TOKEN or not CHAT_ID:
        print("❌ ERREUR : TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID non configuré")
        return
    
    message = construire_message()
    
    if message is None:
        print("ℹ️ Aucune activation R147 détectée pour demain. Pas d'envoi Telegram.")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    try:
        response = requests.post(
            url, 
            data={
                "chat_id": CHAT_ID, 
                "text": message, 
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Alerte Telegram envoyée avec succès")
        else:
            print(f"❌ Échec de l'envoi : {response.status_code}")
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi Telegram : {e}")

if __name__ == "__main__":
    envoyer_alerte()
