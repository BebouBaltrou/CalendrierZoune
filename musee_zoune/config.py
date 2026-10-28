"""Réglages de l'application."""

import os
import sys
from pathlib import Path

VERSION = "1.1"
RACINE = Path(__file__).resolve().parent.parent


def dossier_donnees() -> Path:
    """Où sont la base, les réglages et le journal.

    - variable d'environnement MUSEE_ZOUNE_DONNEES si elle est définie (tests) ;
    - version installée (exécutable) : %LOCALAPPDATA%\\MuseeZoune ;
    - version de développement : dossier `data/` du projet.
    """
    if os.environ.get("MUSEE_ZOUNE_DONNEES"):
        return Path(os.environ["MUSEE_ZOUNE_DONNEES"])
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "MuseeZoune"
    return RACINE / "data"


DOSSIER_DONNEES = dossier_donnees()
CHEMIN_BASE = DOSSIER_DONNEES / "musee.db"
CHEMIN_JOURNAL = DOSSIER_DONNEES / "sync.log"

SITE = "https://www.blmk.de"
URL_CALENDRIER = f"{SITE}/kalender/"
URL_API = f"{SITE}/wp-json/tribe/events/v1/events"
FUSEAU = "Europe/Berlin"

USER_AGENT = f"MuseeZoune/{VERSION} (outil interne de la communication BLMK)"
DELAI_ENTRE_REQUETES = 1.0  # secondes, une requête à la fois
TIMEOUT = 30
PAR_PAGE = 50
MAX_PAGES = 20

# En dessous de cette proportion d'événements actifs retrouvés,
# on considère que le site a eu un problème et on ne marque rien comme annulé.
SEUIL_PRUDENCE = 0.5
