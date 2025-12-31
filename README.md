# 🛩️ ATIS Dynamique - Atlantic Air Park (LF8523)

Ce projet génère automatiquement une page web ATIS bilingue (Français/Anglais) pour l'aérodrome, incluant les données météo réelles, les zones RTBA et des consignes locales personnalisables.

## 🚀 Fonctionnalités
- **Météo :** Moyenne automatique des METAR de LFBH (La Rochelle) et LFRI (La Roche-sur-Yon).
- **Vent :** Affichage de la direction, force et rafales maximales.
- **Audio :** Génération de voix de synthèse bilingue (Henri & Thomas) via Edge-TTS.
- **NOTAM :** Surveillance automatique de l'activation des zones **R147** et **R45A**.
- **Mise à jour :** Toutes les 30 minutes via GitHub Actions.

## ✍️ Modifier les consignes locales (Remarques)
Il n'est pas nécessaire de toucher au code pour changer les messages de sécurité (travaux, péril aviaire, etc.). Tout se gère via les **Secrets** de GitHub.

### Syntaxe du Secret `ATIS_REMARQUES`
1. Allez dans **Settings** > **Secrets and variables** > **Actions**.
2. Modifiez le secret `ATIS_REMARQUES`.
3. Utilisez le format suivant :
   `Ligne FR 1 | Ligne FR 2 :: Line EN 1 | Line EN 2`

**Raccourcis clavier utiles (Mac) :**
- Le trait vertical `|` (Pipe) : `Option (⌥)` + `Maj (⇧)` + `L`
- Les deux-points `:` : Touche `.` (ou `Maj` + `/`)

**Exemple concret :**
`Piste en herbe fermée | Attention travaux :: Grass runway closed | Caution works`

## 🛠️ Structure technique
- `script.py` : Le moteur Python qui récupère les données et génère le HTML/Audio.
- `.github/workflows/atis.yml` : Le chef d'orchestre qui lance le script à 10 et 40 de chaque heure.
- `index.html` : La page web générée.
- `atis.mp3` : Le fichier audio bilingue généré.

## ⚠️ Avertissement Légal
Ce service est une aide à l'information. Seule la documentation officielle (SIA / Météo-France) fait foi pour la préparation des vols.
