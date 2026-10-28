"""Captures d'écran et PDF d'exemple, sur une COPIE de la base (la vraie n'est pas modifiée).

    .venv\\Scripts\\python outils\\captures.py [dossier_captures]
"""

import os
import sqlite3
import sys
import tempfile
from datetime import date, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from musee_zoune import config, db, textes  # noqa: E402
from musee_zoune.app.__main__ import preparer_apparence  # noqa: E402
from musee_zoune.app.donnees import periode_perso  # noqa: E402
from musee_zoune.app.fenetre import FenetrePrincipale  # noqa: E402


def copie_base() -> sqlite3.Connection:
    source = sqlite3.connect(config.CHEMIN_BASE)
    conn = db.connecter(":memory:")
    source.backup(conn)
    source.close()
    conn.row_factory = sqlite3.Row
    # la copie ne garde que la programmation du musée : pas les posts ni la vie perso réels
    conn.executescript("DELETE FROM post_events; DELETE FROM posts; DELETE FROM vie_perso;")
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

    def uid(debut, jour=""):
        return conn.execute("SELECT uid FROM events WHERE title LIKE ? AND start LIKE ? ORDER BY start",
                            (debut + "%", jour + "%")).fetchone()[0]

    fons = "programm/fons-hickmann"
    visite_fons = uid("Führung – in „Fons Hickmann", "2026-10-29")
    db.ajouter_post(conn, "instagram", "2026-10-02", "publie", "Carrousel des affiches",
                    titre="Ouverture Fons Hickmann", evenements=[fons])
    db.ajouter_post(conn, "instagram", "2026-10-27T18:00", "prevu", "Story + rappel la veille",
                    titre="Visites de la semaine", evenements=[visite_fons, uid("Führung – in „Ungebremste")])
    db.ajouter_post(conn, "facebook", "2026-10-25", "publie", evenements=[uid("Ferienkurs – Manga", "2026-10-29")])
    db.ajouter_post(conn, "newsletter", "2026-11-03", "prevu", "Toute la programmation de novembre",
                    titre="Newsletter de novembre")
    db.ajouter_post(conn, "instagram", "2026-11-12", "prevu", titre="Coulisses de l'accrochage")
    db.ajouter_post(conn, "facebook", "2026-10-30", "publie", "Atelier Halloween : photos des enfants",
                    evenements=[uid("Ferienkurs – Halloween")])
    db.ajouter_post(conn, "instagram", "2026-11-04T12:00", "prevu", "Rappel visite de jeudi",
                    evenements=[uid("Führung – in „Ungebremste")])
    return conn


def capturer(widget, chemin: Path) -> None:
    from PySide6.QtCore import QCoreApplication, QEventLoop
    for _ in range(5):  # laisser la mise en page se terminer (sections reconstruites)
        QCoreApplication.sendPostedEvents()
        QApplication.processEvents(QEventLoop.AllEvents, 50)
    widget.grab().save(str(chemin))
    print("capture :", chemin)


def captures_outils(fenetre, conn, sortie: Path) -> None:
    """Dialogue de nouveau post, compression (fichiers temporaires) et PDF d'exemple."""
    from PIL import Image

    from musee_zoune.app.dialogues import DialoguePost
    from musee_zoune.app.export_pdf import exporter
    from musee_zoune.app.outils import DialogueCompression

    dialogue = DialoguePost(conn, fenetre, precoches=["programm/fons-hickmann"])
    dialogue.titre.setText("Dernières semaines Fons Hickmann")
    dialogue.show()
    capturer(dialogue, sortie / "dialogue_post_fr.png")
    dialogue.close()

    dossier = Path(tempfile.mkdtemp(prefix="zoune_"))
    fichiers = []
    for nom, taille in (("vernissage_falten.jpg", (4032, 3024)), ("affiche_plenkers.png", (3000, 4200))):
        bruit = Image.frombytes("L", taille, os.urandom(taille[0] * taille[1]))
        Image.merge("RGB", [bruit, Image.linear_gradient("L").resize(taille), bruit]).save(
            dossier / nom, quality=95)
        fichiers.append(dossier / nom)
    compression = DialogueCompression(fenetre)
    compression.ajouter(fichiers)
    compression.show()
    compression._lancer()
    compression.fil.wait()
    QApplication.processEvents()
    capturer(compression, sortie / "compression_fr.png")
    compression.close()

    docs = sortie.parent
    exporter(conn, docs / "exemple_calendrier_novembre_2026.pdf", "mois", date(2026, 11, 1), compact=True)
    exporter(conn, docs / "exemple_semaine_45_2026.pdf", "semaine", date(2026, 11, 2))
    print("PDF d'exemple :", docs)


def main() -> None:
    sortie = Path(sys.argv[1] if len(sys.argv) > 1 else "captures")
    sortie.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    preparer_apparence(app)
    conn = copie_base()
    for langue in ("fr", "de"):
        db.ecrire_reglage(conn, "langue", langue)
        db.ecrire_reglage(conn, "mois_compact", "0")
        textes.choisir_langue(langue)
        fenetre = FenetrePrincipale(conn, synchroniser_au_demarrage=False)
        fenetre.resize(1600, 960)
        fenetre.show()

        fenetre.aller_a(date(2026, 11, 2), vue=0)
        capturer(fenetre, sortie / f"vue_mois_{langue}.png")

        fenetre.aller_a(date(2026, 10, 26), vue=1)
        el = next(e for e in fenetre.vue_semaine.elements if "Fons Hickmann" in e.titre and e.nature == "expo")
        fenetre._element_clique(el)
        fenetre.vue_semaine.update()
        capturer(fenetre, sortie / f"vue_semaine_{langue}.png")
        fenetre.panneau.hide()

        if langue == "fr":
            fenetre.act_compact.setChecked(True)
            fenetre.aller_a(date(2026, 11, 2), vue=0)
            capturer(fenetre, sortie / "vue_mois_compact_fr.png")
            fenetre.act_compact.setChecked(False)
            fenetre._montrer_aposter()
            capturer(fenetre, sortie / "a_poster_fr.png")
            fenetre._montrer_posts()
            capturer(fenetre, sortie / "posts_fr.png")
            captures_outils(fenetre, conn, sortie)
        fenetre.close()
    conn.close()


if __name__ == "__main__":
    main()
