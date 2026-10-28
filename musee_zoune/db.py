"""Base SQLite locale (data/musee.db)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date as date_cls
from datetime import datetime, timedelta
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    uid           TEXT PRIMARY KEY,   -- chemin de l'URL de la fiche
    source_id     INTEGER,            -- identifiant numérique côté site (indicatif)
    title         TEXT NOT NULL,
    kicker        TEXT,               -- sur-titre en gras sur le site
    type          TEXT NOT NULL,      -- exposition / visite / atelier / ...
    categories    TEXT NOT NULL DEFAULT '[]',  -- JSON, slugs du site
    start         TEXT NOT NULL,      -- AAAA-MM-JJTHH:MM, heure de Berlin
    end           TEXT,
    all_day       INTEGER NOT NULL DEFAULT 0,
    venue         TEXT,
    address       TEXT,
    city          TEXT,
    description   TEXT,
    url           TEXT NOT NULL,
    image         TEXT,
    status        TEXT NOT NULL DEFAULT 'prevu',  -- prevu / annule / reporte / retire / passe
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);

CREATE TABLE IF NOT EXISTS changes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    event_uid TEXT NOT NULL REFERENCES events(uid),
    kind      TEXT NOT NULL,   -- ajout / modification / annulation
    details   TEXT NOT NULL DEFAULT '{}',  -- JSON : champs modifiés, motif
    at        TEXT NOT NULL    -- horodatage local ISO
);
CREATE INDEX IF NOT EXISTS idx_changes_at ON changes(at);

CREATE TABLE IF NOT EXISTS sync_runs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    at        TEXT NOT NULL,
    source    TEXT NOT NULL,
    total     INTEGER NOT NULL,
    summary   TEXT NOT NULL DEFAULT '{}'
);

-- Vie de Zoune : vacances, week-ends, rendez-vous perso
CREATE TABLE IF NOT EXISTS vie_perso (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    titre     TEXT NOT NULL,
    type      TEXT NOT NULL DEFAULT 'autre',  -- vacances / weekend / rdv / autre
    debut     TEXT NOT NULL,   -- AAAA-MM-JJTHH:MM
    fin       TEXT NOT NULL,
    journee   INTEGER NOT NULL DEFAULT 1,     -- 1 = journée(s) entière(s)
    note      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_vie_perso_debut ON vie_perso(debut);

-- Couleur attribuée une fois pour toutes à chaque exposition
CREATE TABLE IF NOT EXISTS expo_couleurs (
    uid       TEXT PRIMARY KEY,
    couleur   INTEGER NOT NULL   -- index dans la palette
);

-- Posts de communication associés à un événement ou une exposition
CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_uid  TEXT NOT NULL REFERENCES events(uid),
    reseau     TEXT NOT NULL,              -- instagram / facebook / newsletter / autre
    date       TEXT NOT NULL,              -- AAAA-MM-JJ (date prévue ou de publication)
    statut     TEXT NOT NULL DEFAULT 'prevu',  -- prevu / publie
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_event ON posts(event_uid);

-- Réglages : langue, dernier changement consulté…
CREATE TABLE IF NOT EXISTS reglages (
    cle       TEXT PRIMARY KEY,
    valeur    TEXT NOT NULL
);
"""

TYPES_PERSO = ("vacances", "weekend", "rdv", "autre")
RESEAUX = ("instagram", "facebook", "newsletter", "autre")
STATUTS_POST = ("prevu", "publie")

# Champs comparés d'une synchronisation à l'autre.
CHAMPS_SUIVIS = (
    "title", "type", "start", "end", "venue", "city",
    "description", "status", "image", "categories",
)

ACTIFS = ("prevu", "annule", "reporte")  # encore attendus sur le site


def connecter(chemin: Path | str = config.CHEMIN_BASE) -> sqlite3.Connection:
    if str(chemin) != ":memory:":
        Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(chemin)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def ligne_vers_dict(ligne: sqlite3.Row) -> dict:
    d = dict(ligne)
    d["categories"] = json.loads(d.get("categories") or "[]")
    d["all_day"] = bool(d.get("all_day"))
    return d


def evenements(conn: sqlite3.Connection) -> dict[str, dict]:
    return {r["uid"]: ligne_vers_dict(r) for r in conn.execute("SELECT * FROM events")}


def inserer(conn: sqlite3.Connection, ev: dict, maintenant: str) -> None:
    conn.execute(
        """INSERT INTO events (uid, source_id, title, kicker, type, categories, start, end,
               all_day, venue, address, city, description, url, image, status,
               first_seen, last_seen, updated_at)
           VALUES (:uid, :source_id, :title, :kicker, :type, :categories, :start, :end,
               :all_day, :venue, :address, :city, :description, :url, :image, :status,
               :now, :now, :now)""",
        {**ev, "categories": json.dumps(ev["categories"], ensure_ascii=False),
         "all_day": int(ev["all_day"]), "now": maintenant},
    )


def mettre_a_jour(conn: sqlite3.Connection, ev: dict, maintenant: str, modifie: bool) -> None:
    conn.execute(
        f"""UPDATE events SET source_id=:source_id, title=:title, kicker=:kicker, type=:type,
               categories=:categories, start=:start, end=:end, all_day=:all_day, venue=:venue,
               address=:address, city=:city, description=:description, url=:url, image=:image,
               status=:status, last_seen=:now{", updated_at=:now" if modifie else ""}
           WHERE uid=:uid""",
        {**ev, "categories": json.dumps(ev["categories"], ensure_ascii=False),
         "all_day": int(ev["all_day"]), "now": maintenant},
    )


def changer_statut(conn: sqlite3.Connection, uid: str, statut: str, maintenant: str) -> None:
    conn.execute("UPDATE events SET status=?, updated_at=? WHERE uid=?", (statut, maintenant, uid))


def noter_changement(conn: sqlite3.Connection, uid: str, kind: str, details: dict, maintenant: str) -> None:
    conn.execute(
        "INSERT INTO changes (event_uid, kind, details, at) VALUES (?, ?, ?, ?)",
        (uid, kind, json.dumps(details, ensure_ascii=False), maintenant),
    )


def noter_sync(conn: sqlite3.Connection, maintenant: str, source: str, total: int, resume: dict) -> None:
    conn.execute(
        "INSERT INTO sync_runs (at, source, total, summary) VALUES (?, ?, ?, ?)",
        (maintenant, source, total, json.dumps(resume, ensure_ascii=False)),
    )


def derniers_changements(conn: sqlite3.Connection, limite: int = 50) -> list[dict]:
    lignes = conn.execute(
        """SELECT c.*, e.title, e.start FROM changes c JOIN events e ON e.uid = c.event_uid
           ORDER BY c.id DESC LIMIT ?""",
        (limite,),
    )
    return [{**dict(r), "details": json.loads(r["details"])} for r in lignes]


# --------------------------------------------------------------------------
# Lecture pour l'application
# --------------------------------------------------------------------------

def evenements_entre(conn: sqlite3.Connection, debut: str, fin: str) -> list[dict]:
    """Événements visibles (pas retirés) qui chevauchent [debut, fin[."""
    lignes = conn.execute(
        """SELECT * FROM events
           WHERE status IN ('prevu', 'annule', 'reporte', 'passe')
             AND start < ? AND COALESCE(NULLIF(end, ''), start) >= ?
           ORDER BY start""",
        (fin, debut),
    )
    return [ligne_vers_dict(r) for r in lignes]


def expositions(conn: sqlite3.Connection) -> list[dict]:
    lignes = conn.execute(
        "SELECT * FROM events WHERE type='exposition' AND status != 'retire' ORDER BY start")
    return [ligne_vers_dict(r) for r in lignes]


def changements_depuis(conn: sqlite3.Connection, apres_id: int) -> list[dict]:
    lignes = conn.execute(
        """SELECT c.*, e.title, e.start, e.end, e.type, e.url FROM changes c
           JOIN events e ON e.uid = c.event_uid
           WHERE c.id > ? ORDER BY c.at DESC, e.start""",
        (apres_id,),
    )
    return [{**dict(r), "details": json.loads(r["details"])} for r in lignes]


def dernier_changement_id(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COALESCE(MAX(id), 0) FROM changes").fetchone()[0]


# --------------------------------------------------------------------------
# Réglages
# --------------------------------------------------------------------------

def lire_reglage(conn: sqlite3.Connection, cle: str, defaut: str | None = None) -> str | None:
    ligne = conn.execute("SELECT valeur FROM reglages WHERE cle=?", (cle,)).fetchone()
    return ligne[0] if ligne else defaut


def ecrire_reglage(conn: sqlite3.Connection, cle: str, valeur: str) -> None:
    conn.execute(
        "INSERT INTO reglages (cle, valeur) VALUES (?, ?) "
        "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
        (cle, valeur),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Couleurs des expositions
# --------------------------------------------------------------------------

def couleurs_expos(conn: sqlite3.Connection) -> dict[str, int]:
    return {r["uid"]: r["couleur"] for r in conn.execute("SELECT * FROM expo_couleurs")}


def enregistrer_couleurs(conn: sqlite3.Connection, couleurs: dict[str, int]) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO expo_couleurs (uid, couleur) VALUES (?, ?)", couleurs.items())
    conn.commit()


# --------------------------------------------------------------------------
# Vie de Zoune (CRUD)
# --------------------------------------------------------------------------

def _verifier_perso(titre: str, type_: str, debut: str, fin: str) -> None:
    if not titre.strip():
        raise ValueError("titre vide")
    if type_ not in TYPES_PERSO:
        raise ValueError(f"type inconnu : {type_}")
    if fin < debut:
        raise ValueError("fin avant début")


def ajouter_perso(conn: sqlite3.Connection, titre: str, type_: str, debut: str, fin: str,
                  journee: bool = True, note: str = "") -> int:
    _verifier_perso(titre, type_, debut, fin)
    cur = conn.execute(
        "INSERT INTO vie_perso (titre, type, debut, fin, journee, note) VALUES (?, ?, ?, ?, ?, ?)",
        (titre.strip(), type_, debut, fin, int(journee), note),
    )
    conn.commit()
    return cur.lastrowid


def modifier_perso(conn: sqlite3.Connection, id_: int, titre: str, type_: str, debut: str,
                   fin: str, journee: bool = True, note: str = "") -> None:
    _verifier_perso(titre, type_, debut, fin)
    conn.execute(
        "UPDATE vie_perso SET titre=?, type=?, debut=?, fin=?, journee=?, note=? WHERE id=?",
        (titre.strip(), type_, debut, fin, int(journee), note, id_),
    )
    conn.commit()


def supprimer_perso(conn: sqlite3.Connection, id_: int) -> None:
    conn.execute("DELETE FROM vie_perso WHERE id=?", (id_,))
    conn.commit()


def lire_perso(conn: sqlite3.Connection, id_: int) -> dict | None:
    ligne = conn.execute("SELECT * FROM vie_perso WHERE id=?", (id_,)).fetchone()
    return _perso_dict(ligne) if ligne else None


def perso_entre(conn: sqlite3.Connection, debut: str, fin: str) -> list[dict]:
    lignes = conn.execute(
        "SELECT * FROM vie_perso WHERE debut < ? AND fin >= ? ORDER BY debut", (fin, debut))
    return [_perso_dict(r) for r in lignes]


def tout_perso(conn: sqlite3.Connection) -> list[dict]:
    return [_perso_dict(r) for r in conn.execute("SELECT * FROM vie_perso ORDER BY debut")]


def _perso_dict(ligne: sqlite3.Row) -> dict:
    d = dict(ligne)
    d["journee"] = bool(d["journee"])
    return d


# --------------------------------------------------------------------------
# Posts
# --------------------------------------------------------------------------

def _verifier_post(reseau: str, date_: str, statut: str) -> None:
    if reseau not in RESEAUX:
        raise ValueError(f"réseau inconnu : {reseau}")
    if statut not in STATUTS_POST:
        raise ValueError(f"statut inconnu : {statut}")
    datetime.fromisoformat(date_)  # lève ValueError si la date est invalide


def ajouter_post(conn: sqlite3.Connection, event_uid: str, reseau: str, date_: str,
                 statut: str = "prevu", note: str = "") -> int:
    _verifier_post(reseau, date_, statut)
    cur = conn.execute(
        "INSERT INTO posts (event_uid, reseau, date, statut, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (event_uid, reseau, date_, statut, note, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return cur.lastrowid


def modifier_post(conn: sqlite3.Connection, id_: int, reseau: str, date_: str,
                  statut: str, note: str = "") -> None:
    _verifier_post(reseau, date_, statut)
    conn.execute("UPDATE posts SET reseau=?, date=?, statut=?, note=? WHERE id=?",
                 (reseau, date_, statut, note, id_))
    conn.commit()


def supprimer_post(conn: sqlite3.Connection, id_: int) -> None:
    conn.execute("DELETE FROM posts WHERE id=?", (id_,))
    conn.commit()


def lire_post(conn: sqlite3.Connection, id_: int) -> dict | None:
    ligne = conn.execute("SELECT * FROM posts WHERE id=?", (id_,)).fetchone()
    return dict(ligne) if ligne else None


def posts_de(conn: sqlite3.Connection, event_uid: str) -> list[dict]:
    lignes = conn.execute("SELECT * FROM posts WHERE event_uid=? ORDER BY date, id", (event_uid,))
    return [dict(r) for r in lignes]


def etat_posts(conn: sqlite3.Connection) -> dict[str, str]:
    """uid -> 'publie' (au moins un post publié) ou 'prevu' (seulement prévus).

    Les événements absents du dictionnaire n'ont aucun post.
    """
    lignes = conn.execute(
        "SELECT event_uid, MAX(statut = 'publie') AS publie FROM posts GROUP BY event_uid")
    return {r["event_uid"]: "publie" if r["publie"] else "prevu" for r in lignes}


def a_poster(conn: sqlite3.Connection, aujourdhui: date_cls, jours: int = 7) -> list[dict]:
    """Événements prévus qui commencent dans les `jours` prochains jours et n'ont aucun post."""
    debut = aujourdhui.isoformat()
    fin = (aujourdhui + timedelta(days=jours + 1)).isoformat()
    lignes = conn.execute(
        """SELECT * FROM events e
           WHERE e.status = 'prevu' AND e.start >= ? AND e.start < ?
             AND NOT EXISTS (SELECT 1 FROM posts p WHERE p.event_uid = e.uid)
           ORDER BY e.start""",
        (debut, fin),
    )
    return [ligne_vers_dict(r) for r in lignes]
