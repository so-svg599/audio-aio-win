# AudioPlayerAIO

Lecteur audio de bureau en français pour Windows, développé avec Python, PySide6/Qt Multimedia et SQLite.

## Fonctionnalités

- Indexation récursive de dossiers audio locaux, métadonnées et pochettes via Mutagen, bibliothèque SQLite et lecture Qt Multimedia.
- Recherche locale par titre, artiste, album et genre; bibliothèque, playlists locales, favoris et lectures récentes.
- Skins à mises en page distinctes, sélectionnables à chaud et mémorisées : **Windows Media Player 7/8** (bibliothèque argentée, navigation verticale), **Windows Media Player 9/10 XP Luna** (panneau latéral, playlist à droite et gros Play rond), **Windows Media Player 11 Vista** (onglets Now Playing/Library/Rip/Burn/Sync, barre glossy et transport sombre), **Windows Media Player 12 Windows 10** (interface plate, commandes centrées en bas), et les skins existants **Windows Vista/7 Aero**, **Windows 10/11 Metro/Fluent**, **Sombre**, **Clair**. Le panneau Now Playing affiche la pochette et un visualiseur animé. La case **Mode sombre** est séparée et peut se combiner aux skins.
- Barre de progression seekable: position stockée à la seconde (conversion vers millisecondes pour Qt), affichage durant le glissement et seek au relâchement. Les flux non seekables désactivent le slider.
- Sources **YouTube** et **SoundCloud** à navigation Accueil, Playlists, Uploads, Historique et Aimé; recherche et lecture en streaming avec `yt-dlp` exécutées en arrière-plan. Les onglets utilisent les flux et URL reconnus par les extracteurs, tentent un repli si l’URL principale échoue et indiquent l’URL secondaire utilisée.
- Cookies YouTube/SoundCloud pris en charge depuis un fichier ou le navigateur local (Chrome, Firefox, Edge, Brave, Opera ou Vivaldi). Les pages personnalisées (playlists, historique, aimés) nécessitent généralement des cookies de compte; sans cookies, yt-dlp peut refuser les flux privés. YouTube Uploads accepte un identifiant/URL de chaîne optionnel. SoundCloud accepte un nom de profil ou URL permalink pour Reposts, Playlists, Uploads et Aimé; sans profil, Accueil présente une recherche de tendances. Son onglet Historique est local à l’application et conserve jusqu’à 100 titres SoundCloud dont la lecture a été résolue.
- Connexion pCloud via API REST officielle, région US ou EU, identifiants ou jeton; parcours récursif des fichiers audio et lecture via lien de fichier. Le login gère la vérification 2FA (saisie du code puis `tfa_login`) et mémorise le jeton d’authentification retourné.
- Contrôles de lecture dessinés avec Qt, précédent/suivant, arrêt, volume, répétition et aléatoire. Fermer le dialogue Paramètres ne ferme que ce dialogue. Fermer la fenêtre principale quitte l’application, sauf si l’icône de notification est activée et disponible, auquel cas elle est masquée dans le tray.
- Option de zone de notification avec commandes Lecture/Pause, Précédent, Suivant, Afficher et Quitter.

## Skins

Choisissez un skin dans **Paramètres → Général → Thème (application immédiate)**. Le choix est enregistré dans `settings.json`; la case **Mode sombre** peut se combiner aux skins. Les compositions sont réorganisées selon la famille WMP (navigation latérale, panneaux Now Playing/bibliothèque, onglets dédiés et barre de transport); il ne s’agit pas uniquement de couleurs.

## Services et confidentialité

Les services tiers et les fonctionnalités personnalisées dépendent de l’accès réseau, des comptes et des changements apportés par les fournisseurs. Maintenez `yt-dlp` à jour (`pip install -U yt-dlp`). Aucun secret n’est fourni avec le projet. Les cookies, mots de passe et jetons configurés sont stockés dans `settings.json` sans chiffrement : protégez ce fichier et ne le partagez pas. Les URL de streaming peuvent expirer ou être refusées. Les codecs disponibles dépendent de Qt Multimedia et du système.

pCloud utilise `api.pcloud.com` (US) ou `eapi.pcloud.com` (EU) et les endpoints `userinfo`, `tfa_login`, `listfolder` et `getfilelink`. L’authentification 2FA utilise les paramètres `token`, `code` et `trustdevice=1`; les identifiants et jetons demeurent en clair dans `settings.json`. Les services SMB/FTP et WebDAV ne sont pas connectés dans cette version; leurs profils restent configurables dans Paramètres.

## Installation (Windows 10/11)

1. Installer Python 3.10 ou supérieur.
2. À la racine du dépôt :

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python main.py
   ```

3. Utiliser **Ajouter des dossiers** pour indexer la musique locale. Configurez les services dans **Paramètres**.

Les données de l’application sont placées sous `%APPDATA%\AudioPlayerAIO\` (base SQLite et `settings.json`).

## Build Windows

Exécuter `build_windows.bat`, ou manuellement :

```powershell
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm AudioPlayerAIO.spec
```

Le build doit être exécuté sur Windows pour produire un exécutable natif. GitHub Actions compile et publie un artefact Windows x64.

## Vérifications développeur

```bash
python -m py_compile main.py
QT_QPA_PLATFORM=offscreen python main.py
```

L’instanciation hors écran nécessite les dépendances Qt natives (dont OpenGL sous Linux). Les essais `yt-dlp` réels nécessitent Internet et peuvent être restreints par les services et les cookies.

## Licence

Licence MIT. Voir [LICENSE](LICENSE).
