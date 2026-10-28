"""Export PDF du calendrier."""

from datetime import date, datetime
from pathlib import Path

import pymupdf
import pytest

from musee_zoune import db, textes
from musee_zoune.scraper import parser_html
from musee_zoune.sync import synchroniser

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn():
    c = db.connecter(":memory:")
    evs = parser_html((FIXTURES / "kalender.html").read_text(encoding="utf-8"))
    synchroniser(c, evs, "html", datetime(2026, 10, 28, 21, 0))
    db.ajouter_perso(c, "Dentiste", "rdv", "2026-11-05T14:30", "2026-11-05T15:15", False)
    yield c
    c.close()


def _texte(chemin):
    doc = pymupdf.open(chemin)
    try:
        assert doc.page_count == 1
        page = doc[0]
        assert page.rect.width > page.rect.height  # paysage
        assert abs(page.rect.width - 842) < 3 and abs(page.rect.height - 595) < 3  # A4
        return page.get_text()
    finally:
        doc.close()


@pytest.mark.parametrize("compact", [False, True])
def test_export_mois(app, conn, tmp_path, compact):
    from musee_zoune.app.export_pdf import exporter
    chemin = exporter(conn, tmp_path / "mois.pdf", "mois", date(2026, 11, 1), compact=compact)
    texte = _texte(chemin)
    assert "Novembre 2026" in texte
    assert "Fons Hickmann" in texte  # légende des expositions
    assert "Dentiste" in texte


def test_export_semaine_sans_vie_perso(app, conn, tmp_path):
    from musee_zoune.app.export_pdf import exporter
    chemin = exporter(conn, tmp_path / "s.pdf", "semaine", date(2026, 11, 5), avec_perso=False)
    texte = _texte(chemin)
    assert "Semaine 45" in texte and "Dentiste" not in texte


def test_export_en_allemand(app, conn, tmp_path):
    from musee_zoune.app.export_pdf import exporter, nom_fichier
    try:
        textes.choisir_langue("de")
        chemin = exporter(conn, tmp_path / "de.pdf", "mois", date(2026, 11, 1))
        assert "November 2026" in _texte(chemin)
        assert nom_fichier("mois", date(2026, 11, 1)) == "BLMK_November_2026.pdf"
    finally:
        textes.choisir_langue("fr")
