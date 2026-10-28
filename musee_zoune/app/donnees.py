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
    etat_post: str | None = None   # None = aucun post, "prevu", "publie" (pour un post : son statut)
    infobulle: str = ""            # texte affiché au survol (vide = titre)

    @property
    def premier_jour(self) -> date:
        return self.debut.date()

    @property
    def dernier_jour(self) -> date:
        if self.fin.time() == time(0, 0) and self.fin.date() > self.debut.date():
            return self.fin.date() - timedelta(days=1)
        return max(self.fin.date(), self.debut.date())


class Donnees:
    """Modèle commun aux vues : événements, vie perso et posts libres, après filtres."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.ville: str | None = None              # filtre « un seul lieu » (export)
        self.villes_masquees: set[str] = set()
        self.types_masques: set[str] = set()       # types d'événements décochés
        self.expos_masquees: set[str] = set()
        self.perso_masques: set[str] = set()       # types de vie perso décochés
        self.sans_post_seulement = False
        self.avec_perso = True
        self.avec_posts = True                     # posts affichés dans le calendrier
        self.recherche = ""
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
            "SELECT DISTINCT city FROM events WHERE city != '' AND status != 'retire' ORDER BY city")
        return [r[0] for r in lignes]

    def types(self) -> list[str]:
        presents = {r[0] for r in self.conn.execute(
            "SELECT DISTINCT type FROM events WHERE status != 'retire'")}
        ordre = ["exposition", "vernissage", "visite", "atelier", "concert", "evenement", "annonce", "autre"]
        return [t_ for t_ in ordre if t_ in presents]

    def couleur_expo(self, uid: str) -> str:
        return cal.PALETTE[self.couleurs.get(uid, 0) % len(cal.PALETTE)]

    # ------------------------------------------------------------------

    def _ville_ok(self, ville: str | None) -> bool:
        if self.ville and ville != self.ville:
            return False
        return (ville or "") not in self.villes_masquees

    def _recherche_ok(self, *textes: str | None) -> bool:
        if not self.recherche.strip():
            return True
        cible = cal.normaliser(" ".join(x or "" for x in textes))
        return all(mot in cible for mot in cal.normaliser(self.recherche).split())

    def elements(self, debut: date, fin: date) -> list[Element]:
        """Tout ce qui chevauche [debut, fin] (inclus), filtres appliqués."""
        d, f = debut.isoformat(), (fin + timedelta(days=1)).isoformat()
        resultat = []
        etats = db.etat_posts(self.conn)
        for ev in db.evenements_entre(self.conn, d, f):
            est_expo = ev["type"] == "exposition"
            if (not self._ville_ok(ev.get("city"))
                    or ev["type"] in self.types_masques
                    or (est_expo and ev["uid"] in self.expos_masquees)
                    or (self.sans_post_seulement and ev["uid"] in etats)
                    or not self._recherche_ok(ev["title"], ev.get("venue"), ev.get("city"),
                                              ev.get("description"))):
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
                etat_post=etats.get(ev["uid"]),
            ))
        if self.avec_perso:
            for p in db.perso_entre(self.conn, d, f):
                if p["type"] in self.perso_masques or not self._recherche_ok(p["titre"], p.get("note")):
                    continue
                resultat.append(Element(
                    cle=f"perso:{p['id']}", nature="perso", titre=p["titre"],
                    couleur=cal.COULEUR_PERSO, debut=cal.dt(p["debut"]), fin=cal.dt(p["fin"]),
                    journee=p["journee"], source=p,
                ))
        if self.avec_posts and not self.sans_post_seulement:
            for post in db.posts_entre(self.conn, d, f):
                if not self._recherche_ok(post["titre"], post.get("note"), post["reseau"]):
                    continue
                moment = datetime.fromisoformat(post["date"])
                a_une_heure = len(post["date"]) > 10
                resultat.append(Element(
                    cle=f"post:{post['id']}", nature="post", titre=libelle_post(post),
                    couleur=cal.theme.COULEUR_ACCENT, debut=moment,
                    fin=moment + timedelta(minutes=30) if a_une_heure else moment,
                    journee=not a_une_heure, source=post, etat_post=post["statut"],
                    infobulle=infobulle_post(self.conn, post),
                ))
        return resultat

    def expos_visibles(self, debut: date, fin: date) -> list[dict]:
        """Expositions de la période (colonne de gauche, légende du PDF)."""
        resultat = []
        for e in self.expos:
            premier, dernier = cal.jours_de(e)
            if dernier < debut or premier > fin or not self._ville_ok(e.get("city")):
                continue
            resultat.append(e)
        return resultat


def libelle_post(post: dict, longueur: int = 60) -> str:
    """Libellé dans le calendrier : réseau + début de la note (ou le titre)."""
    from ..textes import t
    texte = " ".join((post.get("note") or post.get("titre") or "").split())
    if len(texte) > longueur:
        texte = texte[:longueur].rsplit(" ", 1)[0] + "…"
    reseau = t("reseau_" + post["reseau"])
    return f"{reseau} · {texte}" if texte else reseau


def infobulle_post(conn: sqlite3.Connection, post: dict) -> str:
    """Détail complet au survol : réseau, date, statut, titre, note, événements liés."""
    from ..textes import date_lisible, t
    moment = datetime.fromisoformat(post["date"])
    quand = date_lisible(moment.date(), longue=True) + (f", {moment:%H:%M}" if len(post["date"]) > 10 else "")
    lignes = [f"{t('reseau_' + post['reseau'])} — {quand} — {t('post_statut_' + post['statut'])}"]
    if post.get("titre"):
        lignes.append(post["titre"])
    if post.get("note"):
        lignes.append(post["note"])
    if post["evenements"]:
        titres = [r[0] for r in conn.execute(
            f"SELECT title FROM events WHERE uid IN ({','.join('?' * len(post['evenements']))}) ORDER BY start",
            post["evenements"])]
        lignes.append(t("post_couvre", n=len(titres)) + " :")
        lignes += [f"  • {x}" for x in titres]
    else:
        lignes.append(t("post_libre"))
    return "\n".join(lignes)


def titre_post(post: dict) -> str:
    """« Instagram · Newsletter de novembre » (ou le réseau seul)."""
    from ..textes import t
    reseau = t("reseau_" + post["reseau"])
    return f"{reseau} · {post['titre']}" if post.get("titre") else reseau


def periode_perso(debut: date, fin: date, journee: bool,
                  heure_debut: time = time(0, 0), heure_fin: time = time(23, 59)) -> tuple[str, str]:
    """Bornes stockées pour un élément de vie perso."""
    if journee:
        return (datetime.combine(debut, time(0, 0)).isoformat(timespec="minutes"),
                datetime.combine(fin, time(23, 59)).isoformat(timespec="minutes"))
    return (datetime.combine(debut, heure_debut).isoformat(timespec="minutes"),
            datetime.combine(fin, heure_fin).isoformat(timespec="minutes"))


def notification_a_faire(conn: sqlite3.Connection, aujourdhui: date) -> bool:
    """Vrai si le rappel « à poster » n'a pas encore été notifié aujourd'hui."""
    return db.lire_reglage(conn, "derniere_notif_a_poster") != aujourdhui.isoformat()


def noter_notification(conn: sqlite3.Connection, aujourdhui: date) -> None:
    db.ecrire_reglage(conn, "derniere_notif_a_poster", aujourdhui.isoformat())


def echeance(jour: date, aujourdhui: date) -> str:
    """« aujourd'hui », « demain », « dans 3 jours »."""
    from ..textes import t
    n = (jour - aujourdhui).days
    if n <= 0:
        return t("aposter_aujourdhui")
    if n == 1:
        return t("aposter_demain")
    return t("aposter_dans", n=n)
