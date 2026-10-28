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
- Captures : `docs/captures/` (régénérer avec `.venv\Scripts\python outils\captures.py docs\captures`).

### Sources

- API REST de The Events Calendar : `/wp-json/tribe/events/v1/events?ends_after=<maintenant>`
  (inclut les expositions déjà ouvertes, comme la page /kalender/).
- Page `/kalender/` : bloc JSON-LD schema.org (statut annulé / reporté) ; secours si l'API ne répond pas.

### Fichiers

- `musee_zoune/scraper.py` : téléchargement et parsing
- `musee_zoune/db.py` : schéma SQLite (`events`, `changes`, `sync_runs`, `vie_perso`, `expo_couleurs`, `reglages`)
- `musee_zoune/sync.py` : comparaison et résumé
- `musee_zoune/textes.py` : tous les textes affichés (FR et DE)
- `musee_zoune/config.py` : réglages
- `musee_zoune/calendrier.py` : couleurs des expositions, liens expo, mise en page (sans Qt)
- `musee_zoune/app/` : interface PySide6 (fenêtre, vues mois/semaine, panneaux, dialogues)
