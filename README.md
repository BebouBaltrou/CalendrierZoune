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

Synchronisation quotidienne automatique : `planifier_sync.ps1` (voir l'en-tête du script).

### Sources

- API REST de The Events Calendar : `/wp-json/tribe/events/v1/events?ends_after=<maintenant>`
  (inclut les expositions déjà ouvertes, comme la page /kalender/).
- Page `/kalender/` : bloc JSON-LD schema.org (statut annulé / reporté) ; secours si l'API ne répond pas.

### Fichiers

- `musee_zoune/scraper.py` : téléchargement et parsing
- `musee_zoune/db.py` : schéma SQLite (`events`, `changes`, `sync_runs`)
- `musee_zoune/sync.py` : comparaison et résumé
- `musee_zoune/textes.py` : tous les textes affichés (FR, DE à venir)
- `musee_zoune/config.py` : réglages
