import requests
import os
import re
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def scanner_notams():
    """
    Scanne les NOTAM pour R147 (même méthode que script.py)
    Retourne aussi l'année complète pour validation
    """
    status = {
        "R147": {"info": "pas d'information", "date": "", "annee": ""}
    }
    
    # MÉTHODE 1 : Site AZBA du SIA (source officielle)
    try:
        url = "https://www.sia.aviation-civile.gouv.fr/schedules"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            texte = res.text
            
            # R147 avec date
            match_r147 = re.search(r'(\d{2})/(\d{2})/(\d{4}).*?R\s*147.*?(\d{2}):?(\d{2})[^\d]*(\d{2}):?(\d{2})', texte, re.IGNORECASE | re.DOTALL)
            if match_r147:
                jour, mois, annee = match_r147.group(1), match_r147.group(2), match_r147.group(3)
                h1, m1, h2, m2 = match_r147.group(4), match_r147.group(5), match_r147.group(6), match_r147.group(7)
                status["R147"]["date"] = f"{jour}/{mois}"
                status["R147"]["annee"] = annee
                status["R147"]["info"] = f"active {h1}h{m1}-{h2}h{m2}Z"
            
            if status["R147"]["info"] != "pas d'information":
                return status
    except Exception as e:
        print(f"Erreur méthode 1: {e}")
    
    # MÉTHODE 2 : NOTAM Web (bulletin R)
    try:
        url = "https://notamweb.aviation-civile.gouv.fr/Script/IHM/Bul_R.php?ZoneRglmt=RTBA"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            texte = res.text
            
            if 'R147' in texte or 'R 147' in texte:
                match = re.search(r'R\s*147.*?C(\d{10})/(\d{10})', texte, re.DOTALL)
                if match:
                    debut, fin = match.group(1), match.group(2)
                    annee, mois, jour = "20" + debut[0:2], debut[2:4], debut[4:6]
                    h_debut = f"{debut[6:8]}:{debut[8:10]}"
                    h_fin = f"{fin[6:8]}:{fin[8:10]}"
                    status["R147"]["date"] = f"{jour}/{mois}"
                    status["R147"]["annee"] = annee
                    status["R147"]["info"] = f"active {h_debut}-{h_fin}Z"
                elif 'R147' in texte:
                    status["R147"]["info"] = "active (voir NOTAM)"
            
            if status["R147"]["info"] != "pas d'information":
                return status
    except Exception as e:
        print(f"Erreur méthode 2: {e}")
    
    # MÉTHODE 3 : FAA (dernier recours)
    try:
        url_proxy = "https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html")
        res = requests.get(url_proxy, timeout=20)
        
        if res.status_code == 200:
            import json
            data = json.loads(res.text)
            texte = data.get('contents', '').upper()
            
            if texte:
                match = re.search(r"R147.*?(\d{4}).*?TO.*?(\d{4})", texte)
                if match:
                    h1, h2 = match.group(1), match.group(2)
                    status["R147"]["info"] = f"active {h1[:2]}h{h1[2:]}-{h2[:2]}h{h2[2:]}Z"
    except Exception as e:
        print(f"Erreur méthode 3: {e}")
    
    return status

def construire_message():
    """
    Construit le message Telegram avec les infos NOTAM
    Valide que la date correspond bien à demain
    """
    maintenant = datetime.now()
    demain = maintenant + timedelta(days=1)
    demain_str = demain.strftime("%d/%m/%Y")
    
    rapport = f"📅 *PRÉVISIONS ZONE R147 POUR DEMAIN ({demain_str})*\n"
    rapport += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    notams = scanner_notams()
    r147 = notams["R147"]
    
    # Vérification : est-ce que la date du NOTAM correspond à demain ?
    notam_valide_pour_demain = False
    
    if r147["date"] and r147["annee"]:
        try:
            # Construire la date complète du NOTAM
            jour, mois = r147["date"].split("/")
            date_notam = datetime(int(r147["annee"]), int(mois), int(jour))
            
            # Comparer avec demain (ignorer l'heure)
            if date_notam.date() == demain.date():
                notam_valide_pour_demain = True
            elif date_notam.date() < maintenant.date():
                # NOTAM périmé (date passée)
                notam_valide_pour_demain = False
            else:
                # Date dans le futur (après-demain, etc.) → ne pas alerter
                notam_valide_pour_demain = False
        except Exception as e:
            print(f"Erreur validation date: {e}")
            # En cas d'erreur de parsing, on affiche quand même
            notam_valide_pour_demain = True
    elif "active" in r147["info"].lower():
        # Pas de date précise mais marqué actif → on alerte
        notam_valide_pour_demain = True
    
    if "active" in r147["info"].lower() and notam_valide_pour_demain:
        # ALERTE : Zone active demain
        rapport += "🚨 *ALERTE ZONE MILITAIRE*\n\n"
        rapport += f"📍 *R147 CHARENTE*\n"
        rapport += f"⏰ Horaires : `{r147['info']}`\n"
        rapport += f"📅 Date : `{r147['date']}`\n"
        rapport += "\n⚠️ *Prudence lors de votre navigation demain.*\n"
        rapport += "✈️ Vérifiez les NOTAM officiels avant tout vol.\n"
    else:
        # Pas d'activation prévue pour demain OU pas d'info fiable
        rapport += "⚠️ *R147 CHARENTE*\n"
        rapport += "Statut inconnu ou aucune activation détectée.\n"
        rapport += "\n📋 *Vérifiez impérativement les NOTAM officiels :*\n"
        rapport += "• https://notamweb.aviation-civile.gouv.fr\n"
        rapport += "• https://www.sia.aviation-civile.gouv.fr\n"
        rapport += "\n⚠️ Ne présumez JAMAIS qu'une zone est inactive sans vérification officielle.\n"
    
    rapport += f"\n🕐 Mise à jour : {maintenant.strftime('%d/%m/%Y %H:%M')}"
    
    return rapport

def envoyer_alerte():
    """
    Envoie le message sur Telegram
    """
    if not TOKEN or not CHAT_ID:
        print("❌ ERREUR : TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID non configuré")
        return
    
    message = construire_message()
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
            print(f"❌ Erreur Telegram : {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi : {e}")

if __name__ == "__main__":
    envoyer_alerte()
