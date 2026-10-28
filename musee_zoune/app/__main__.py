"""Lancement : python -m musee_zoune.app"""

import sys

from PySide6.QtWidgets import QApplication

from .. import db
from ..sync import configurer_journal
from .fenetre import FenetrePrincipale


def preparer_apparence(app: QApplication) -> None:
    """Thème sombre façon Google Agenda pour toute l'application."""
    from PySide6.QtGui import QFont

    from ..theme import POLICE, feuille_de_style
    police = QFont(POLICE)
    police.setPointSizeF(10)
    app.setFont(police)
    app.setStyleSheet(feuille_de_style())


def main() -> int:
    configurer_journal()
    app = QApplication(sys.argv)
    app.setApplicationName("Musée Zoune")
    app.setStyle("Fusion")
    preparer_apparence(app)
    conn = db.connecter()
    fenetre = FenetrePrincipale(conn)
    fenetre.show()
    code = app.exec()
    conn.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
