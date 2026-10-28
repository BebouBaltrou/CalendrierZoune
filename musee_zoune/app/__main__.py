"""Lancement : python -m musee_zoune.app"""

import sys

from PySide6.QtWidgets import QApplication

from .. import db
from ..sync import configurer_journal
from .fenetre import FenetrePrincipale


def main() -> int:
    configurer_journal()
    app = QApplication(sys.argv)
    app.setApplicationName("Musée Zoune")
    app.setStyle("Fusion")
    conn = db.connecter()
    fenetre = FenetrePrincipale(conn)
    fenetre.show()
    code = app.exec()
    conn.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
