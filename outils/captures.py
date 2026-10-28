"""Captures d'écran des vues, sur une COPIE de la base (la vraie n'est pas modifiée).

    .venv\\Scripts\\python outils\\captures.py [dossier_sortie]
"""

import sqlite3
import sys
from datetime import date, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from musee_zoune import config, db, textes  # noqa: E402
from musee_zoune.app.donnees import periode_perso  # noqa: E402
from musee_zoune.app.fenetre import FenetrePrincipale  # noqa: E402


def copie_base() -> sqlite3.Connection:
    source = sqlite3.connect(config.CHEMIN_BASE)
    conn = db.connecter(":memory:")
    source.backup(conn)
    source.close()
    conn.row_factory = sqlite3.Row
    exemples = [
        ("Week-end à Berlin", "weekend", date(2026, 11, 7), date(2026, 11, 8), True, None, None),
        ("Dentiste", "rdv", date(2026, 11, 5), date(2026, 11, 5), False, time(14, 30), time(15, 15)),
        ("Réunion presse", "rdv", date(2026, 11, 3), date(2026, 11, 3), False, time(9, 0), time(10, 0)),
        ("Vacances de Noël", "vacances", date(2026, 12, 21), date(2027, 1, 2), True, None, None),
        ("Congé", "vacances", date(2026, 11, 19), date(2026, 11, 20), True, None, None),
    ]
    for titre, type_, d, f, journee, hd, hf in exemples:
        debut, fin = periode_perso(d, f, journee, hd or time(0, 0), hf or time(23, 59))
        db.ajouter_perso(conn, titre, type_, debut, fin, journee)
    return conn


def capturer(fenetre, chemin: Path) -> None:
    QApplication.processEvents()
    fenetre.grab().save(str(chemin))
    print("capture :", chemin)


def main() -> None:
    sortie = Path(sys.argv[1] if len(sys.argv) > 1 else "captures")
    sortie.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    conn = copie_base()
    for langue in ("fr", "de"):
        db.ecrire_reglage(conn, "langue", langue)
        textes.choisir_langue(langue)
        fenetre = FenetrePrincipale(conn, synchroniser_au_demarrage=False)
        fenetre.resize(1500, 950)
        fenetre.show()

        fenetre.aller_a(date(2026, 11, 2), vue=0)
        el = next(e for e in fenetre.vue_mois.elements if "Ungebremste" in e.titre and e.nature == "event")
        fenetre._element_clique(el)
        fenetre.vue_mois.update()
        capturer(fenetre, sortie / f"vue_mois_{langue}.png")

        fenetre.aller_a(date(2026, 11, 2), vue=1)
        el = next(e for e in fenetre.vue_semaine.elements if "Ungebremste" in e.titre and e.nature == "event")
        fenetre._element_clique(el)
        fenetre.vue_semaine.update()
        capturer(fenetre, sortie / f"vue_semaine_{langue}.png")

        if langue == "fr":
            fenetre.dock_chg.raise_()
            capturer(fenetre, sortie / "changements_fr.png")
            fenetre.aller_a(date(2026, 12, 1), vue=0)
            capturer(fenetre, sortie / "vue_mois_decembre_fr.png")
        fenetre.close()
    conn.close()


if __name__ == "__main__":
    main()
