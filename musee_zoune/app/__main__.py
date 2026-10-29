"""Lancement : python -m musee_zoune.app (ou « Musee Zoune.exe »)."""

import json
import logging
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from .. import config, db, maj
from ..sync import configurer_journal
from .fenetre import FenetrePrincipale

log = logging.getLogger("musee_zoune.app")


def preparer_apparence(app: QApplication) -> None:
    """Thème sombre façon Google Agenda pour toute l'application."""
    from PySide6.QtGui import QFont

    from ..theme import POLICE, feuille_de_style
    police = QFont(POLICE)
    police.setPointSizeF(10)
    app.setFont(police)
    app.setStyleSheet(feuille_de_style())


def _erreur_non_geree(type_, valeur, trace) -> None:
    """Sans console (exécutable), une erreur doit être visible et journalisée."""
    texte = "".join(traceback.format_exception(type_, valeur, trace))
    log.error("erreur non gérée :\n%s", texte)
    if QApplication.instance():
        QMessageBox.critical(None, "Musée Zoune",
                             f"Une erreur inattendue s'est produite.\n\n{valeur}\n\n"
                             f"Détails dans : {config.CHEMIN_JOURNAL}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    configurer_journal()
    sys.excepthook = _erreur_non_geree
    if maj.appliquer_en_attente():
        return 0  # une mise à jour préparée s'installe, l'application va se relancer
    maj.nettoyer()
    app = QApplication(argv)
    app.setApplicationName("Musée Zoune")
    app.setStyle("Fusion")
    preparer_apparence(app)
    conn = db.connecter()
    fenetre = FenetrePrincipale(conn)
    fenetre.show()
    if "--autotest" in argv:
        _autotest(app, fenetre, Path(argv[argv.index("--autotest") + 1]))
    else:
        fenetre.maj.demarrage()  # mode automatique : vérification quelques secondes après l'ouverture
    code = app.exec()
    conn.close()
    return code


def _autotest(app: QApplication, fenetre: FenetrePrincipale, rapport: Path) -> None:
    """Vérification de l'exécutable sans intervention : synchro, compression, export PDF.

    Usage interne : « Musee Zoune.exe --autotest rapport.json ».
    """
    from datetime import date

    from PySide6.QtCore import QTimer

    resultat: dict = {"version": config.VERSION, "donnees": str(config.DOSSIER_DONNEES)}

    def etape_finale():
        try:
            from PIL import Image

            from .. import compression
            from .export_pdf import exporter
            resultat["evenements"] = fenetre.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            resultat["sync_runs"] = fenetre.conn.execute("SELECT COUNT(*) FROM sync_runs").fetchone()[0]
            resultat["posts"] = fenetre.conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            resultat["vie_perso"] = fenetre.conn.execute("SELECT COUNT(*) FROM vie_perso").fetchone()[0]
            fenetre.aller_a(date.today(), vue=0)
            resultat["posts_dans_le_calendrier"] = sum(
                1 for e in fenetre.vue_mois.elements if getattr(e, "nature", "") == "post")
            dossier = rapport.parent
            photo = dossier / "autotest.jpg"
            Image.new("RGB", (4000, 3000), (40, 120, 200)).save(photo, quality=95)
            r = compression.compresser(photo, compression.PREREGLAGES["mail"])
            resultat["compression"] = {"ok": r.ok, "avant": r.avant, "apres": r.apres, "message": r.message}
            heic = dossier / "autotest.heic"
            Image.new("RGB", (2000, 1500), (200, 80, 40)).save(heic)
            r = compression.compresser(heic, compression.PREREGLAGES["web"])
            resultat["heic"] = {"ok": r.ok, "message": r.message}
            pdf = exporter(fenetre.conn, dossier / "autotest.pdf", "mois", date.today(), compact=True)
            r = compression.compresser(pdf, compression.PREREGLAGES["mail"])
            resultat["export_pdf"] = pdf.stat().st_size
            resultat["compression_pdf"] = {"ok": r.ok, "message": r.message}
            from PySide6.QtCore import QEventLoop
            for _ in range(5):
                app.processEvents(QEventLoop.AllEvents, 50)
            fenetre.grab().save(str(dossier / "autotest.png"))
            resultat["ok"] = True
        except Exception:  # noqa: BLE001
            resultat["ok"] = False
            resultat["erreur"] = traceback.format_exc()
        rapport.write_text(json.dumps(resultat, indent=2, ensure_ascii=False), encoding="utf-8")
        app.quit()

    essais = [0]

    def attendre_sync():
        essais[0] += 1
        if fenetre.fil and fenetre.fil.isRunning() and essais[0] < 120:
            QTimer.singleShot(1000, attendre_sync)
        else:
            etape_finale()

    QTimer.singleShot(2000, attendre_sync)


if __name__ == "__main__":
    sys.exit(main())
