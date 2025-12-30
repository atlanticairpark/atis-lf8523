def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        metar = response.text.split('\n')[1]
        
        # --- HEURE ---
        time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
        h_tele = f"{time_match.group(2)}:{time_match.group(3)}"
        
        # --- VENT (Gestion CALM, VRB et GUSTS) ---
        w_dir_txt = "000"
        w_spd_txt = "0"
        w_audio_fr = ""
        w_audio_en = ""

        if "00000KT" in metar:
            w_dir_txt = "CALME"
            w_spd_txt = "0"
            w_audio_fr = "vent calme"
            w_audio_en = "wind calm"
        else:
            # Cherche le vent : Direction(3)Vitesse(2) avec option Rafale(G+2)
            w_match = re.search(r' ([A-Z0-9]{3})(\d{2})(G\d{2})?KT', metar)
            if w_match:
                dir_raw = w_match.group(1) # Ex: 230 ou VRB
                spd_raw = w_match.group(2).lstrip('0') or "0" # Ex: 08 -> 8
                gust_raw = w_match.group(3) # Ex: G25 ou None
                
                # Direction
                if dir_raw == "VRB":
                    w_dir_txt = "VRB"
                    w_audio_fr = "vent variable"
                    w_audio_en = "wind variable"
                else:
                    w_dir_txt = dir_raw
                    w_audio_fr = f"vent {dir_raw} degrés"
                    w_audio_en = f"wind {dir_raw} degrees"
                
                # Vitesse et Rafales
                if gust_raw:
                    gust_spd = gust_raw.replace('G', '').lstrip('0')
                    w_spd_txt = f"{spd_raw}-{gust_spd}"
                    w_audio_fr += f", {spd_raw} nœuds, rafales {gust_spd} nœuds"
                    w_audio_en += f", {spd_raw} knots, gusts {gust_spd} knots"
                else:
                    w_spd_txt = spd_raw
                    w_audio_fr += f", {spd_raw} nœuds"
                    w_audio_en += f", {spd_raw} knots"

        # --- QNH / TEMP / DEW (inchangé) ---
        q_match = re.search(r'Q(\d{4})', metar)
        q_val = q_match.group(1) if q_match else "1013"
        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        temp = t_match.group(1).replace('M', '-')
        dew = t_match.group(2).replace('M', '-')
        
        return {
            "heure_metar": h_tele,
            "qnh": q_val,
            "q_audio": ", ".join(list(q_val)),
            "temp": temp,
            "dew": dew,
            "w_dir_visu": w_dir_txt,
            "w_spd_visu": w_spd_txt,
            "w_audio_fr": w_audio_fr,
            "w_audio_en": w_audio_en
        }
    except:
        return None
