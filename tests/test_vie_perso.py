"""Vie de Zoune (CRUD), réglages, premier lancement du jour, traductions."""

from datetime import date, datetime, time

import pytest

from musee_zoune import db, textes
from musee_zoune.app.donnees import Donnees, periode_perso
from musee_zoune.sync import derniere_sync, sync_necessaire


@pytest.fixture
def conn():
    c = db.connecter(":memory:")
    yield c
    c.close()


def test_crud_vie_perso(conn):
    debut, fin = periode_perso(date(2026, 12, 21), date(2026, 12, 24), journee=True)
    id_ = db.ajouter_perso(conn, "Vacances Noël", "vacances", debut, fin)
    assert db.lire_perso(conn, id_)["fin"] == "2026-12-24T23:59"

    db.modifier_perso(conn, id_, "Vacances de Noël", "vacances", debut, "2026-12-27T23:59")
    element = db.lire_perso(conn, id_)
    assert element["titre"] == "Vacances de Noël" and element["fin"] == "2026-12-27T23:59"

    assert [p["id"] for p in db.perso_entre(conn, "2026-12-25", "2026-12-26")] == [id_]
    assert db.perso_entre(conn, "2027-01-05", "2027-01-06") == []

    db.supprimer_perso(conn, id_)
    assert db.lire_perso(conn, id_) is None and db.tout_perso(conn) == []


def test_rdv_avec_heures_affiche_dans_les_vues(conn):
    debut, fin = periode_perso(date(2026, 11, 5), date(2026, 11, 5), journee=False,
                               heure_debut=time(14, 30), heure_fin=time(15, 15))
    id_ = db.ajouter_perso(conn, "Dentiste", "rdv", debut, fin, journee=False)
    el = next(e for e in Donnees(conn).elements(date(2026, 11, 2), date(2026, 11, 8))
              if e.cle == f"perso:{id_}")
    assert el.nature == "perso" and not el.journee and el.debut.hour == 14


@pytest.mark.parametrize("titre, type_, debut, fin", [
    ("  ", "rdv", "2026-11-05T10:00", "2026-11-05T11:00"),
    ("Test", "inconnu", "2026-11-05T10:00", "2026-11-05T11:00"),
    ("Test", "rdv", "2026-11-05T10:00", "2026-11-04T11:00"),
])
def test_vie_perso_refuse_donnees_invalides(conn, titre, type_, debut, fin):
    with pytest.raises(ValueError):
        db.ajouter_perso(conn, titre, type_, debut, fin)


def test_reglages(conn):
    assert db.lire_reglage(conn, "langue", "fr") == "fr"
    db.ecrire_reglage(conn, "langue", "de")
    db.ecrire_reglage(conn, "langue", "de")
    assert db.lire_reglage(conn, "langue") == "de"


def test_premier_lancement_du_jour(conn):
    assert derniere_sync(conn) is None
    assert sync_necessaire(conn, datetime(2026, 10, 29, 8, 0))
    db.noter_sync(conn, "2026-10-29T08:01:00", "api", 62, {})
    conn.commit()
    assert not sync_necessaire(conn, datetime(2026, 10, 29, 18, 0))
    assert sync_necessaire(conn, datetime(2026, 10, 30, 7, 0))


def test_textes_complets_en_allemand():
    fr, de = set(textes.TEXTES["fr"]), set(textes.TEXTES["de"])
    assert fr - de == set() and de - fr == set()


def test_choix_langue():
    try:
        textes.choisir_langue("de")
        assert textes.t("vue_semaine") == "Woche"
        assert textes.date_lisible(date(2026, 11, 5)) == "Do. 5. November"
        textes.choisir_langue("fr")
        assert textes.date_lisible(date(2026, 11, 5)) == "jeu. 5 novembre"
    finally:
        textes.choisir_langue("fr")
