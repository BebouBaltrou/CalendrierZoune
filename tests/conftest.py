"""Qt sans écran pour les tests (export PDF).

Sous Windows, la plateforme « offscreen » n'a pas de polices : on garde la plateforme
native (aucune fenêtre n'est affichée par les tests).
"""

import os

if os.name != "nt":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
