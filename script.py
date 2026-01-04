def scanner_notams():
    firs = ["LFRR", "LFFF", "LFEE", "LFMM"]
    status = {"R147": "pas d'information", "R45A": "pas d'information"}
    
    combined_text = ""
    for fir in firs:
        try:
            res = requests.get(f"https://api.allorigins.win/get?url=" + requests.utils.quote(f"https://www.notams.faa.gov/common/icao/{fir}.html"), timeout=10)
            if res.status_code == 200:
                # 1. On nettoie les balises HTML qui pourraient couper les mots (ex: R45<span>A</span>)
                text_clean = re.sub(r'<[^>]+>', ' ', res.text.upper())
                # 2. On normalise les espaces et retours à la ligne
                text_clean = " ".join(text_clean.split())
                combined_text += text_clean + " "
        except:
            continue

    if not combined_text: return status

    for zone in ["R147", "R45A"]:
        # La regex : 
        # - Cherche la zone (ex: R45A)
        # - Saute n'importe quel texte (.+?) de façon non-gourmande
        # - Cherche un groupe de 4 chiffres suivi d'un tiret et 4 chiffres (ex: 1430-1600)
        # On limite la recherche à 200 caractères après la zone pour ne pas prendre l'horaire d'une autre zone
        pattern = rf"{zone}.{{1,200}}?(\d{{4}}[-/]\d{{4}})"
        match = re.search(pattern, combined_text)
        
        if match:
            raw_time = match.group(1).replace('/', '-')
            h_debut = f"{raw_time[:2]}:{raw_time[2:4]}"
            h_fin = f"{raw_time[-4:-2]}:{raw_time[-2:]}"
            status[zone] = f"active de {h_debut} à {h_fin}"
        elif zone in combined_text:
            status[zone] = "citée (vérifier SIA)"
            
    return status
