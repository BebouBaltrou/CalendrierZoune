"""Base SQLite locale (data/musee.db)."""

from __future__ import annotations

import json
import sqlite3
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
"""

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
