"""Tests de la comparaison site / base (base SQLite en mémoire)."""

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from musee_zoune import db
from musee_zoune.scraper import parser_html
from musee_zoune.sync import formater_resume, synchroniser

FIXTURES = Path(__file__).parent / "fixtures"
MAINTENANT = datetime(2026, 10, 28, 21, 0)


@pytest.fixture(scope="module")
def scrapes():
    return parser_html((FIXTURES / "kalender.html").read_text(encoding="utf-8"))


@pytest.fixture
def conn(scrapes):
    c = db.connecter(":memory:")
    synchroniser(c, scrapes, "html", MAINTENANT)
    yield c
    c.close()


def _changes(conn, kind):
    return conn.execute("SELECT * FROM changes WHERE kind=?", (kind,)).fetchall()


def test_premiere_sync_tout_est_ajoute(conn):
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 62
    assert len(_changes(conn, "ajout")) == 62


def test_deuxieme_sync_identique_aucun_changement(conn, scrapes):
    resume = synchroniser(conn, scrapes, "html", MAINTENANT)
    assert not (resume["ajouts"] or resume["modifications"] or resume["annulations"])
    assert "Aucun changement" in formater_resume(resume, MAINTENANT)


def test_modification_horaire(conn, scrapes):
    cible = scrapes[5]
    autres = [ev if ev is not cible else replace(ev, start=ev.start[:11] + "15:30") for ev in scrapes]
    resume = synchroniser(conn, autres, "html", MAINTENANT)
    assert len(resume["modifications"]) == 1
    assert "start" in resume["modifications"][0]["details"]
    texte = formater_resume(resume, MAINTENANT)
    assert "début" in texte and "15:30" in texte


def test_annulation_sur_le_site(conn, scrapes):
    cible = scrapes[10]
    autres = [ev if ev is not cible else replace(ev, status="annule") for ev in scrapes]
    resume = synchroniser(conn, autres, "html", MAINTENANT)
    assert [e["uid"] for e in resume["annulations"]] == [cible.uid]
    statut = conn.execute("SELECT status FROM events WHERE uid=?", (cible.uid,)).fetchone()[0]
    assert statut == "annule"


def test_disparition_evenement_futur_est_une_annulation(conn, scrapes):
    futur = next(ev for ev in scrapes if ev.start > "2026-12-01")
    resume = synchroniser(conn, [ev for ev in scrapes if ev is not futur], "html", MAINTENANT)
    assert [e["uid"] for e in resume["annulations"]] == [futur.uid]
    assert conn.execute("SELECT status FROM events WHERE uid=?", (futur.uid,)).fetchone()[0] == "retire"

    # Il revient : simple modification avec motif
    resume = synchroniser(conn, scrapes, "html", MAINTENANT)
    assert [e["uid"] for e in resume["modifications"]] == [futur.uid]
    assert conn.execute("SELECT status FROM events WHERE uid=?", (futur.uid,)).fetchone()[0] == "prevu"


def test_evenement_termine_devient_passe_sans_annulation(conn, scrapes):
    plus_tard = datetime(2026, 11, 1, 12, 0)
    restants = [ev for ev in scrapes if ev.end >= "2026-11-01T12:00"]
    resume = synchroniser(conn, restants, "html", plus_tard)
    assert resume["annulations"] == []
    assert len(resume["passes"]) == len(scrapes) - len(restants) > 0


def test_prudence_si_le_site_renvoie_presque_rien(conn, scrapes):
    resume = synchroniser(conn, scrapes[:5], "html", MAINTENANT)
    assert resume["prudence"] is True
    assert resume["annulations"] == []
    assert conn.execute("SELECT COUNT(*) FROM events WHERE status='retire'").fetchone()[0] == 0


def test_simulation_n_enregistre_rien(scrapes):
    c = db.connecter(":memory:")
    synchroniser(c, scrapes, "html", MAINTENANT, simulation=True)
    assert c.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
    c.close()


def test_sync_necessaire_une_fois_par_jour(scrapes):
    from musee_zoune.sync import sync_necessaire

    c = db.connecter(":memory:")
    assert sync_necessaire(c, MAINTENANT)  # jamais synchronisé
    synchroniser(c, scrapes, "html", MAINTENANT)
    assert not sync_necessaire(c, MAINTENANT.replace(hour=23))  # même jour
    assert sync_necessaire(c, datetime(2026, 10, 29, 8, 0))  # lendemain
    c.close()
