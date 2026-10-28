"""Prépare ce que les vues affichent, à partir de la base (sans Qt)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from .. import calendrier as cal
from .. import db


@dataclass
class Element:
    cle: str                 # "ev:<uid>" ou "perso:<id>"
    nature: str              # "expo" / "event" / "perso"
    titre: str
    couleur: str
    debut: datetime
    fin: datetime
    journee: bool            # affiché comme bande / en haut de la vue semaine
    annule: bool = False
    expo_liee: str | None = None
    source: dict = field(default_factory=dict)

    @property
    def premier_jour(self) -> date:
        return self.debut.date()

    @property
    def dernier_jour(self) -> date:
        if self.fin.time() == time(0, 0) and self.fin.date() > self.debut.date():
            return self.fin.date() - timedelta(days=1)
        return max(self.fin.date(), self.debut.date())


class Donnees:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.ville: str | None = None
        self.expos_masquees: set[str] = set()
        self.recharger()

    def recharger(self) -> None:
        """Relit les expositions, attribue les couleurs manquantes, refait les liens."""
        self.expos = db.expositions(self.conn)
        existantes = db.couleurs_expos(self.conn)
        nouvelles = cal.attribuer_couleurs(self.expos, existantes)
        if nouvelles:
            db.enregistrer_couleurs(self.conn, nouvelles)
        self.couleurs = {**existantes, **nouvelles}
        self.expos_par_uid = {e["uid"]: e for e in self.expos}
        tous = db.evenements_entre(self.conn, "0000", "9999")
        self.liens = cal.lier_aux_expositions(tous, self.expos)

    def villes(self) -> list[str]:
        lignes = self.conn.execute(
            "SELECT DISTINCT city FROM events WHERE city != '' ORDER BY city")
        return [r[0] for r in lignes]

    def couleur_expo(self, uid: str) -> str:
        return cal.PALETTE[self.couleurs.get(uid, 0) % len(cal.PALETTE)]

    # ------------------------------------------------------------------

    def elements(self, debut: date, fin: date) -> list[Element]:
        """Tout ce qui chevauche [debut, fin] (inclus)."""
        d, f = debut.isoformat(), (fin + timedelta(days=1)).isoformat()
        resultat = []
        for ev in db.evenements_entre(self.conn, d, f):
            if self.ville and ev.get("city") != self.ville:
                continue
            est_expo = ev["type"] == "exposition"
            if est_expo and ev["uid"] in self.expos_masquees:
                continue
            resultat.append(Element(
                cle=f"ev:{ev['uid']}",
                nature="expo" if est_expo else "event",
                titre=ev["title"],
                couleur=cal.couleur_evenement(ev, self.liens, self.couleurs),
                debut=cal.dt(ev["start"]),
                fin=cal.dt(ev.get("end") or ev["start"]),
                journee=est_expo or ev.get("all_day", False),
                annule=ev["status"] in ("annule", "reporte"),
                expo_liee=self.liens.get(ev["uid"]),
                source=ev,
            ))
        for p in db.perso_entre(self.conn, d, f):
            resultat.append(Element(
                cle=f"perso:{p['id']}",
                nature="perso",
                titre=p["titre"],
                couleur=cal.COULEUR_PERSO,
                debut=cal.dt(p["debut"]),
                fin=cal.dt(p["fin"]),
                journee=p["journee"],
                source=p,
            ))
        return resultat

    def expos_visibles(self, debut: date, fin: date) -> list[dict]:
        """Expositions de la période (pour la légende), filtre de lieu appliqué."""
        resultat = []
        for e in self.expos:
            premier, dernier = cal.jours_de(e)
            if dernier < debut or premier > fin:
                continue
            if self.ville and e.get("city") != self.ville:
                continue
            resultat.append(e)
        return resultat


def periode_perso(debut: date, fin: date, journee: bool,
                  heure_debut: time = time(0, 0), heure_fin: time = time(23, 59)) -> tuple[str, str]:
    """Bornes stockées pour un élément de vie perso."""
    if journee:
        return (datetime.combine(debut, time(0, 0)).isoformat(timespec="minutes"),
                datetime.combine(fin, time(23, 59)).isoformat(timespec="minutes"))
    return (datetime.combine(debut, heure_debut).isoformat(timespec="minutes"),
            datetime.combine(fin, heure_fin).isoformat(timespec="minutes"))
