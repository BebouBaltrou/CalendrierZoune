# Musée Zoune

Outils pour automatiser la communication du BLMK (Brandenburgisches Landesmuseum für moderne Kunst).

## Étape 1 : programmation

Récupère les événements à venir de https://www.blmk.de/kalender/ et garde l'historique des changements
(ajouts, modifications, annulations) dans une base SQLite locale (`data/musee.db`).

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m musee_zoune.sync              # synchroniser
.venv\Scripts\python -m musee_zoune.sync --simulation # voir les changements sans enregistrer
.venv\Scripts\python -m pytest                        # tests
```

La synchronisation se fait automatiquement au premier lancement de l'application dans la journée
(et via le bouton « Actualiser »). En ligne de commande : `python -m musee_zoune.sync --si-necessaire`.

## Étape 2 : application de bureau

Double-cliquer sur `lancer.bat` (crée l'environnement Python au premier lancement).
Ou : `.venv\Scripts\python -m musee_zoune.app`.

- Vue **Mois** : expositions en bandes colorées sur leur période, autres événements en pastilles.
  Bouton « Compact » (mémorisé) : bandes fines sans texte (nom au survol), le mois tient à l'écran.
  Les visites et vernissages prennent la couleur de leur exposition.
- Vue **Semaine** : créneaux horaires, titre complet, lieu, type ; clic = détails.
- **Vie de Zoune** : vacances, week-ends, rendez-vous (hachurés violets). Double-clic sur un jour
  (vue mois) ou un créneau (vue semaine) pour en ajouter ; bouton « Vie de Zoune… » pour la liste.
- **Changements** : bandeau + panneau des ajouts / modifications / annulations non lus.
- Langue FR / DE (menu en haut à droite, mémorisée).

## Étape 3 : suivi des posts et rappels

- **Posts** : depuis le panneau Détails d'un événement (« Ajouter un post… »), le bouton « + » ou la
  liste des posts (réseau Instagram / Facebook / newsletter / autre, date, statut, titre, note).
- **Indicateur** sur les événements à venir, dans les deux vues : pastille orange = pas encore de post,
  cercle bleu = post prévu, coche verte = post publié. Case « Sans post uniquement » dans la colonne gauche.
- **À poster** : onglet + bandeau orange listant les événements des 7 prochains jours sans aucun post,
  mis à jour au lancement et après chaque synchronisation.
- **Notification Windows** (zone de notification) une fois par jour, au premier lancement, s'il reste
  des événements à poster.
- Captures : `docs/captures/` (régénérer avec `.venv\Scripts\python outils\captures.py docs\captures`).

### Sources

- API REST de The Events Calendar : `/wp-json/tribe/events/v1/events?ends_after=<maintenant>`
  (inclut les expositions déjà ouvertes, comme la page /kalender/).
- Page `/kalender/` : bloc JSON-LD schema.org (statut annulé / reporté) ; secours si l'API ne répond pas.

### Fichiers

- `musee_zoune/scraper.py` : téléchargement et parsing
- `musee_zoune/db.py` : schéma SQLite (`events`, `changes`, `sync_runs`, `vie_perso`, `posts`, `post_events`, `expo_couleurs`, `reglages`)
- `musee_zoune/sync.py` : comparaison et résumé
- `musee_zoune/textes.py` : tous les textes affichés (FR et DE)
- `musee_zoune/config.py` : réglages
- `musee_zoune/calendrier.py` : couleurs des expositions, liens expo, mise en page (sans Qt)
- `musee_zoune/app/` : interface PySide6 (fenêtre, vues mois/semaine, panneaux, dialogues)

## Étape 4 : outils

Menu **Outils** de la barre du haut :

- **Compresser des fichiers…** : glisser-déposer ou choisir des photos (JPG, PNG, HEIC, WEBP, TIFF)
  et des PDF. Préréglages « Mail » (moins de 2 Mo, photos 1600 px), « Web » (1200 px, qualité 80),
  « Impression » (3500 px, qualité 92) ou personnalisé. Les fichiers compressés sont créés à côté des
  originaux avec un suffixe (`photo_mail.jpg`) ; les originaux ne sont jamais modifiés.
  Photos : Pillow + pillow-heif ; PDF : PyMuPDF (réduction des images intégrées). Aucun logiciel à installer.
- **Exporter le calendrier en PDF…** : vue mois (compacte ou non) ou semaine, A4 paysage, légende des
  couleurs, avec ou sans la Vie de Zoune, dans la langue de l'interface.
  Exemples : `docs/exemple_calendrier_novembre_2026.pdf`, `docs/exemple_semaine_45_2026.pdf`.

## Design (thème sombre façon Google Agenda)

- Toutes les couleurs et la feuille de style sont dans `musee_zoune/theme.py` (thème SOMBRE pour
  l'application, CLAIR pour l'export PDF).
- Barre du haut : ☰ (replier la colonne gauche), « Aujourd'hui », ‹ ›, titre de la période, recherche,
  choix Mois / Semaine, Compact, Actualiser, cloche à badge (changements + à poster), ⋯ (posts, Vie de
  Zoune, compression, export PDF), langue FR / DE.
- Colonne gauche : mini-calendrier (clic = aller à la date), cases à cocher colorées par exposition,
  type, lieu, type de Vie de Zoune, filtre « Sans post uniquement » et « Posts libres ».
- Panneau de droite (s'ouvre au clic) : Détails, Changements, À poster, Posts.
- Bouton « + » flottant : nouvel élément de Vie de Zoune ou nouveau post.

## Posts : plusieurs événements par post

Un post peut couvrir zéro, un ou plusieurs événements (table `post_events`). À la création, on coche
les événements concernés (avec recherche) ; sans case cochée, c'est un post « libre ». Un événement n'est couvert que s'il est explicitement coché :
un post sur une exposition ne couvre pas ses visites. Les anciennes bases sont migrées automatiquement.

Tous les posts (liés ou libres) apparaissent dans le calendrier à leur date, avec un post-it jaune
(coche verte = publié) : à l'heure prévue dans la vue semaine si une heure est indiquée, sinon en
ligne « journée ». Libellé : réseau + début de la note ; survol = détail et événements liés ;
clic = détail du post. Case « Posts dans le calendrier » (colonne gauche) pour les masquer.

## Version à envoyer (exécutable Windows)

```powershell
.venv\Scripts\pip install pyinstaller
.venv\Scripts\python outils\construire_paquet.py
```

Produit `dist/MuseeZoune-1.0-windows.zip` : l'application (aucun Python à installer), un LISEZMOI
FR/DE, le code source (`source/`, exigé par la licence AGPL de PyMuPDF) et les licences des
bibliothèques. Dans la version installée, les données sont dans `%LOCALAPPDATA%\MuseeZoune`
(base vide au départ, remplie par la première synchronisation). La version de développement
(`lancer.bat`) garde ses données dans `data/`.

## Mises à jour automatiques (depuis la 1.2)

Menu « ⋯ » > « Paramètres… » > « Mises à jour » :

- **Automatiquement au lancement** (par défaut) : quelques secondes après l'ouverture,
  l'application interroge `https://api.github.com/repos/BebouBaltrou/CalendrierZoune/releases/latest`
  (sans jeton, en arrière-plan, en silence si pas d'internet). Si une version plus récente existe,
  elle la télécharge, vérifie son empreinte SHA-256, puis propose « Redémarrer maintenant » ou
  « Plus tard » (installation à la fermeture, active au lancement suivant).
- **Manuellement** : le bouton « Rechercher les mises à jour » affiche la nouvelle version et ses
  notes, et propose de l'installer.

La version de développement (`lancer.bat`) affiche seulement l'information, sans rien installer.

L'exe en cours ne peut pas être remplacé (PyInstaller relit le code dans l'exe à chaque import) :
le nouveau contenu est préparé dans `Musee Zoune.maj` à côté du dossier de l'application, puis un
script PowerShell attend la fermeture, échange les fichiers (anciens renommés en `.old`, retour
arrière en cas d'échec) et relance si demandé. `%LOCALAPPDATA%\MuseeZoune` n'est jamais touché.
Journal du script : `%TEMP%\MuseeZoune-maj.log`.

### Publier une version

1. Monter `VERSION` dans `musee_zoune/config.py`, puis `.venv\Scripts\python outils\construire_paquet.py`.
2. Le script produit dans `dist/` :
   - `MuseeZoune-<v>-windows.zip` (installation complète) ;
   - `MuseeZoune-<v>-maj-depuis-<base>.zip` (mise à jour légère : seul l'exe a changé depuis
     `<base>`, la plus ancienne version publiée compatible) ;
   - un fichier `.sha256` pour chaque zip.
3. Créer la release GitHub `v<v>` et y joindre **tous** ces fichiers (zips et `.sha256`).

Si les bibliothèques ont changé (pas de mise à jour légère possible), le script le signale :
ne joindre que le zip complet et son `.sha256`, et ajouter aux notes de la release la ligne
`<!-- musee-zoune: installation-complete -->` (invisible sur GitHub). L'application téléchargera
alors le zip complet et remplacera tout le dossier de l'application.
