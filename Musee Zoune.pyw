"""Point d'entrée de l'exécutable (PyInstaller)."""

import sys

from musee_zoune.app.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
