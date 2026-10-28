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
    id_ = db.ajouter_post(conn, "instagram", "2026-10-30", "prevu", "carrousel affiches", evenements=[FONS])
    assert db.lire_post(conn, id_)["note"] == "carrousel affiches"
    assert db.etat_posts(conn) == {FONS: "prevu"}

    db.modifier_post(conn, id_, "instagram", "2026-10-31", "publie", "carrousel affiches")
    assert db.lire_post(conn, id_)["evenements"] == [FONS]  # liens inchangés
    assert db.lire_post(conn, id_)["statut"] == "publie"
    assert db.etat_posts(conn) == {FONS: "publie"}

    db.ajouter_post(conn, "newsletter", "2026-11-15", "prevu", evenements=[FONS])
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
        db.ajouter_post(conn, reseau, jour, statut, evenements=[FONS])


# --- Rappel J-7 ---------------------------------------------------------------

def test_a_poster_fenetre_de_7_jours(conn):
    evenements = db.a_poster(conn, AUJOURDHUI)
    debuts = [e["start"] for e in evenements]
    assert debuts and all("2026-10-28" <= d < "2026-11-05" for d in debuts)
    assert "2026-11-05T11:00" not in debuts  # J+8 : pas encore
    assert all(e["type"] != "exposition" or e["start"] >= "2026-10-28" for e in evenements)


def test_un_post_retire_l_evenement_de_la_liste(conn):
    uid = db.a_poster(conn, AUJOURDHUI)[0]["uid"]
    db.ajouter_post(conn, "facebook", "2026-10-28", "prevu", evenements=[uid])
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
    db.ajouter_post(conn, "instagram", "2026-11-01", "publie", evenements=[uid])
    elements = {e.cle: e for e in Donnees(conn).elements(date(2026, 11, 2), date(2026, 11, 8))}
    assert elements[f"ev:{uid}"].etat_post == "publie"
    assert elements[f"ev:{FONS}"].etat_post is None


def test_filtre_sans_post(conn):
    uid = _uid(conn, "Führung – in „Ungebremste")
    db.ajouter_post(conn, "instagram", "2026-11-01", "prevu", evenements=[uid])
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


# --- Plusieurs événements par post, posts libres, migration --------------------------

def test_un_post_couvre_plusieurs_evenements(conn):
    visite = _uid(conn, "Führung – in „Fons Hickmann", "2026-10-29")
    id_ = db.ajouter_post(conn, "instagram", "2026-10-28", evenements=[FONS, visite])
    assert set(db.lire_post(conn, id_)["evenements"]) == {FONS, visite}
    assert set(db.etat_posts(conn)) == {FONS, visite}
    assert visite not in [e["uid"] for e in db.a_poster(conn, AUJOURDHUI)]


def test_post_sur_expo_ne_couvre_pas_ses_visites(conn):
    visite = _uid(conn, "Führung – in „Fons Hickmann", "2026-10-29")
    db.ajouter_post(conn, "instagram", "2026-10-28", evenements=[FONS])
    assert visite not in db.etat_posts(conn)
    assert visite in [e["uid"] for e in db.a_poster(conn, AUJOURDHUI)]


def test_modifier_les_liens(conn):
    visite = _uid(conn, "Führung – in „Fons Hickmann", "2026-10-29")
    id_ = db.ajouter_post(conn, "facebook", "2026-10-28", evenements=[FONS])
    db.modifier_post(conn, id_, "facebook", "2026-10-28", "prevu", evenements=[visite])
    assert db.lire_post(conn, id_)["evenements"] == [visite]
    db.modifier_post(conn, id_, "facebook", "2026-10-28", "prevu", evenements=[])
    assert db.lire_post(conn, id_)["evenements"] == [] and db.etat_posts(conn) == {}


def test_post_libre_visible_a_sa_date(conn):
    id_ = db.ajouter_post(conn, "newsletter", "2026-11-03", titre="Newsletter de novembre")
    libres = db.posts_libres_entre(conn, "2026-11-02", "2026-11-09")
    assert [p["id"] for p in libres] == [id_] and libres[0]["titre"] == "Newsletter de novembre"
    assert db.posts_libres_entre(conn, "2026-11-04", "2026-11-09") == []
    db.ajouter_post(conn, "instagram", "2026-11-03", evenements=[FONS])
    assert len(db.posts_libres_entre(conn, "2026-11-02", "2026-11-09")) == 1  # lié : pas libre
    assert len(db.tous_posts(conn)) == 2


def test_supprimer_post_supprime_les_liens(conn):
    id_ = db.ajouter_post(conn, "instagram", "2026-10-28", evenements=[FONS])
    db.supprimer_post(conn, id_)
    assert conn.execute("SELECT COUNT(*) FROM post_events").fetchone()[0] == 0


def test_migration_ancien_modele(tmp_path):
    import sqlite3
    chemin = tmp_path / "ancienne.db"
    ancienne = db.connecter(chemin)
    ancienne.executescript("""
        INSERT INTO events (uid, title, type, start, url, first_seen, last_seen, updated_at)
            VALUES ('programm/x', 'X', 'visite', '2026-11-01T10:00', 'u', 'a', 'a', 'a');
        DROP TABLE post_events;
        DROP TABLE posts;
        CREATE TABLE posts (id INTEGER PRIMARY KEY AUTOINCREMENT, event_uid TEXT NOT NULL,
            reseau TEXT NOT NULL, date TEXT NOT NULL, statut TEXT NOT NULL DEFAULT 'prevu',
            note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE INDEX idx_posts_event ON posts(event_uid);
        INSERT INTO posts (event_uid, reseau, date, statut, note, created_at)
            VALUES ('programm/x', 'instagram', '2026-10-30', 'publie', 'story', '2026-10-28');
    """)
    ancienne.commit()
    ancienne.close()
    conn = db.connecter(chemin)
    post = db.lire_post(conn, 1)
    assert post["evenements"] == ["programm/x"] and post["note"] == "story" and post["titre"] == ""
    assert db.etat_posts(conn) == {"programm/x": "publie"}
    conn.close()
    db.connecter(chemin).close()  # deuxième ouverture : rien à migrer


# --- Posts dans le calendrier (post-it) -------------------------------------------------

def test_tous_les_posts_visibles_a_leur_date(conn):
    from musee_zoune.app.donnees import Donnees
    lie = db.ajouter_post(conn, "instagram", "2026-11-04", "publie", "Carrousel des affiches", evenements=[FONS])
    libre = db.ajouter_post(conn, "newsletter", "2026-11-05T09:30", titre="Newsletter")
    d = Donnees(conn)
    posts = {e.cle: e for e in d.elements(date(2026, 11, 2), date(2026, 11, 8)) if e.nature == "post"}
    assert set(posts) == {f"post:{lie}", f"post:{libre}"}
    e_lie, e_libre = posts[f"post:{lie}"], posts[f"post:{libre}"]
    assert e_lie.journee and e_lie.etat_post == "publie"
    assert e_lie.titre == "Instagram · Carrousel des affiches"
    assert "Fons Hickmann" in e_lie.infobulle
    assert not e_libre.journee and e_libre.debut.hour == 9 and e_libre.debut.minute == 30
    assert e_libre.etat_post == "prevu" and "sans événement" in e_libre.infobulle
    d.avec_posts = False
    assert not [e for e in d.elements(date(2026, 11, 2), date(2026, 11, 8)) if e.nature == "post"]


def test_post_avec_heure_dans_posts_entre(conn):
    db.ajouter_post(conn, "facebook", "2026-11-08T18:00")
    assert len(db.posts_entre(conn, "2026-11-08", "2026-11-09")) == 1
    assert db.posts_entre(conn, "2026-11-09", "2026-11-10") == []


def test_libelle_post_coupe_la_note():
    from musee_zoune.app.donnees import libelle_post
    post = {"reseau": "instagram", "titre": "T", "note": "mot " * 40}
    assert libelle_post(post).startswith("Instagram · mot") and libelle_post(post).endswith("…")
    assert libelle_post({"reseau": "facebook", "titre": "", "note": ""}) == "Facebook"
