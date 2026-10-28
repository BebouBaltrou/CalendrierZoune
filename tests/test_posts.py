"""Posts de communication, rappel J-7, filtre « sans post », notification quotidienne."""

from datetime import date, datetime
from pathlib import Path

import pytest

from musee_zoune import db
from musee_zoune.app.donnees import Donnees, echeance, noter_notification, notification_a_faire
from musee_zoune.scraper import parser_html
from musee_zoune.sync import synchroniser

FIXTURES = Path(__file__).parent / "fixtures"
AUJOURDHUI = date(2026, 10, 28)
FONS = "programm/fons-hickmann"


@pytest.fixture
def conn():
    c = db.connecter(":memory:")
    evs = parser_html((FIXTURES / "kalender.html").read_text(encoding="utf-8"))
    synchroniser(c, evs, "html", datetime(2026, 10, 28, 21, 0))
    yield c
    c.close()


def _uid(conn, debut_titre, jour=None):
    sql = "SELECT uid FROM events WHERE title LIKE ?" + (" AND start LIKE ?" if jour else "")
    params = (debut_titre + "%",) + ((jour + "%",) if jour else ())
    return conn.execute(sql + " ORDER BY start", params).fetchone()[0]


# --- CRUD -------------------------------------------------------------------

def test_crud_post(conn):
    id_ = db.ajouter_post(conn, FONS, "instagram", "2026-10-30", "prevu", "carrousel affiches")
    assert db.lire_post(conn, id_)["note"] == "carrousel affiches"
    assert db.etat_posts(conn) == {FONS: "prevu"}

    db.modifier_post(conn, id_, "instagram", "2026-10-31", "publie", "carrousel affiches")
    assert db.lire_post(conn, id_)["statut"] == "publie"
    assert db.etat_posts(conn) == {FONS: "publie"}

    db.ajouter_post(conn, FONS, "newsletter", "2026-11-15", "prevu")
    assert [p["reseau"] for p in db.posts_de(conn, FONS)] == ["instagram", "newsletter"]
    assert db.etat_posts(conn)[FONS] == "publie"  # au moins un publié

    db.supprimer_post(conn, id_)
    assert db.etat_posts(conn)[FONS] == "prevu"


@pytest.mark.parametrize("reseau, jour, statut", [
    ("tiktok", "2026-10-30", "prevu"),
    ("instagram", "30/10/2026", "prevu"),
    ("instagram", "2026-10-30", "brouillon"),
])
def test_post_invalide_refuse(conn, reseau, jour, statut):
    with pytest.raises(ValueError):
        db.ajouter_post(conn, FONS, reseau, jour, statut)


# --- Rappel J-7 ---------------------------------------------------------------

def test_a_poster_fenetre_de_7_jours(conn):
    evenements = db.a_poster(conn, AUJOURDHUI)
    debuts = [e["start"] for e in evenements]
    assert debuts and all("2026-10-28" <= d < "2026-11-05" for d in debuts)
    assert "2026-11-05T11:00" not in debuts  # J+8 : pas encore
    assert all(e["type"] != "exposition" or e["start"] >= "2026-10-28" for e in evenements)


def test_un_post_retire_l_evenement_de_la_liste(conn):
    uid = db.a_poster(conn, AUJOURDHUI)[0]["uid"]
    db.ajouter_post(conn, uid, "facebook", "2026-10-28", "prevu")
    assert uid not in [e["uid"] for e in db.a_poster(conn, AUJOURDHUI)]


def test_evenement_annule_pas_dans_a_poster(conn):
    uid = db.a_poster(conn, AUJOURDHUI)[0]["uid"]
    conn.execute("UPDATE events SET status='annule' WHERE uid=?", (uid,))
    assert uid not in [e["uid"] for e in db.a_poster(conn, AUJOURDHUI)]


def test_expo_en_cours_pas_dans_a_poster(conn):
    # Fons Hickmann a ouvert le 3/10 : elle ne déclenche pas de rappel J-7
    assert FONS not in [e["uid"] for e in db.a_poster(conn, AUJOURDHUI)]


def test_echeance():
    assert echeance(AUJOURDHUI, AUJOURDHUI) == "aujourd'hui"
    assert echeance(date(2026, 10, 29), AUJOURDHUI) == "demain"
    assert echeance(date(2026, 11, 2), AUJOURDHUI) == "dans 5 jours"


# --- Vues : indicateur et filtre -------------------------------------------------

def test_etat_post_sur_les_elements(conn):
    uid = _uid(conn, "Führung – in „Ungebremste")
    db.ajouter_post(conn, uid, "instagram", "2026-11-01", "publie")
    elements = {e.cle: e for e in Donnees(conn).elements(date(2026, 11, 2), date(2026, 11, 8))}
    assert elements[f"ev:{uid}"].etat_post == "publie"
    assert elements[f"ev:{FONS}"].etat_post is None


def test_filtre_sans_post(conn):
    uid = _uid(conn, "Führung – in „Ungebremste")
    db.ajouter_post(conn, uid, "instagram", "2026-11-01", "prevu")
    donnees = Donnees(conn)
    donnees.sans_post_seulement = True
    cles = {e.cle for e in donnees.elements(date(2026, 11, 2), date(2026, 11, 8))}
    assert f"ev:{uid}" not in cles
    assert f"ev:{FONS}" in cles
    perso = db.ajouter_perso(conn, "Dentiste", "rdv", "2026-11-05T14:00", "2026-11-05T15:00", False)
    cles = {e.cle for e in donnees.elements(date(2026, 11, 2), date(2026, 11, 8))}
    assert f"perso:{perso}" in cles  # la vie perso reste affichée


# --- Notification une fois par jour ------------------------------------------------

def test_notification_une_fois_par_jour(conn):
    assert notification_a_faire(conn, AUJOURDHUI)
    noter_notification(conn, AUJOURDHUI)
    assert not notification_a_faire(conn, AUJOURDHUI)
    assert notification_a_faire(conn, date(2026, 10, 29))
