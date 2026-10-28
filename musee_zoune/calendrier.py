"""Logique d'affichage du calendrier, indépendante de Qt (donc testable).

- couleurs stables des expositions ;
- rattachement des visites / vernissages à leur exposition ;
- répartition des bandes (expositions, vacances) sur des « pistes » ;
- placement côte à côte des événements qui se chevauchent dans la vue semaine.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# Couleurs : voir theme.py (fichier unique pour toute l'interface).
from . import theme  # noqa: E402
from .theme import COULEUR_PERSO, COULEURS_TYPES, PALETTE, SOMBRE  # noqa: E402

COULEUR_PERSO_FOND = SOMBRE.perso_fond


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

def dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def jours_de(element: dict, cle_debut: str = "start", cle_fin: str = "end") -> tuple[date, date]:
    """Premier et dernier jour (inclus) couverts par un événement."""
    debut = dt(element[cle_debut])
    fin = dt(element.get(cle_fin) or element[cle_debut])
    dernier = fin.date()
    if fin.time() == datetime.min.time() and dernier > debut.date():
        dernier -= timedelta(days=1)  # se termine à minuit pile : la veille
    return debut.date(), max(dernier, debut.date())


def lundi_de(d: date) -> date:
    return d - timedelta(days=d.weekday())


def semaines_du_mois(annee: int, mois: int) -> list[date]:
    """Lundis des semaines affichées pour un mois (4 à 6 semaines)."""
    premier = date(annee, mois, 1)
    suivant = date(annee + (mois == 12), mois % 12 + 1, 1)
    lundis, lundi = [], lundi_de(premier)
    while lundi < suivant:
        lundis.append(lundi)
        lundi += timedelta(days=7)
    return lundis


# --------------------------------------------------------------------------
# Couleurs des expositions
# --------------------------------------------------------------------------

def _chevauche(a: tuple[date, date], b: tuple[date, date]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def attribuer_couleurs(expos: list[dict], existantes: dict[str, int],
                       n: int = len(PALETTE)) -> dict[str, int]:
    """Couleurs pour les expositions qui n'en ont pas encore.

    Une couleur déjà attribuée ne change jamais. Pour une nouvelle exposition,
    on évite les couleurs des expositions qui se tiennent en même temps, et
    parmi les couleurs libres on prend la moins utilisée.
    """
    toutes = dict(existantes)
    periodes = {e["uid"]: jours_de(e) for e in expos}
    nouvelles = {}
    for expo in sorted(expos, key=lambda e: (e["start"], e["uid"])):
        uid = expo["uid"]
        if uid in toutes:
            continue
        prises = {toutes[autre] for autre, p in periodes.items()
                  if autre in toutes and autre != uid and _chevauche(p, periodes[uid])}
        usage = [list(toutes.values()).count(i) for i in range(n)]
        libres = [i for i in range(n) if i not in prises] or list(range(n))
        choix = min(libres, key=lambda i: (usage[i], i))
        toutes[uid] = nouvelles[uid] = choix
    return nouvelles


# --------------------------------------------------------------------------
# Rattachement à une exposition
# --------------------------------------------------------------------------

def normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKC", texte or "").lower()
    texte = re.sub(r"[„“”\"«»‚‘’'().,:;!?–—\-/]", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


_CITATION = re.compile(r"[„“\"«‚]([^“”\"»‘]+)[“”\"»‘]")
TOLERANCE_AVANT = timedelta(days=3)  # vernissage la veille de l'ouverture, etc.


def _dans_periode(ev: dict, expo: dict) -> bool:
    debut, fin = jours_de(expo)
    jour = dt(ev["start"]).date()
    return debut - TOLERANCE_AVANT <= jour <= fin


def lier_aux_expositions(evenements: list[dict], expos: list[dict]) -> dict[str, str]:
    """uid d'événement -> uid de l'exposition à laquelle il se rapporte.

    Sur le site, les visites et vernissages citent l'exposition entre
    guillemets : « Führung in „Fons Hickmann. Plakate von heute und davor“ ».
    """
    liens = {}
    for ev in evenements:
        if ev["type"] == "exposition":
            continue
        citations = [normaliser(c) for c in _CITATION.findall(ev["title"])]
        titre = normaliser(ev["title"])
        candidats = []
        for expo in expos:
            cle = normaliser(expo.get("kicker") or expo["title"])
            if len(cle) < 3:
                continue
            if citations:
                ok = any(c.startswith(cle) or cle.startswith(c) for c in citations)
            else:
                ok = len(cle) >= 8 and cle in titre
            if ok and _dans_periode(ev, expo):
                candidats.append(expo)
        if candidats:
            meilleur = max(candidats, key=lambda x: (
                x.get("city") == ev.get("city"), len(x.get("kicker") or "")))
            liens[ev["uid"]] = meilleur["uid"]
    return liens


def couleur_evenement(ev: dict, liens: dict[str, str], couleurs: dict[str, int]) -> str:
    if ev["type"] == "exposition" and ev["uid"] in couleurs:
        return PALETTE[couleurs[ev["uid"]] % len(PALETTE)]
    expo = liens.get(ev["uid"])
    if expo and expo in couleurs:
        return PALETTE[couleurs[expo] % len(PALETTE)]
    return COULEURS_TYPES.get(ev["type"], COULEURS_TYPES["autre"])


# --------------------------------------------------------------------------
# Mise en page
# --------------------------------------------------------------------------

@dataclass
class Bande:
    cle: str
    debut: date  # premier jour visible dans la semaine
    fin: date    # dernier jour visible (inclus)
    piste: int = 0
    coupe_gauche: bool = False  # commence avant la semaine
    coupe_droite: bool = False  # continue après
    y: float = 0                # position verticale (calculée par la vue)
    h: float = 0


def bandes_semaine(elements: list[tuple[str, date, date]], lundi: date) -> list[Bande]:
    """Répartit des périodes (clé, premier jour, dernier jour) sur des pistes."""
    dimanche = lundi + timedelta(days=6)
    visibles = []
    for cle, debut, fin in elements:
        if fin < lundi or debut > dimanche:
            continue
        visibles.append(Bande(cle, max(debut, lundi), min(fin, dimanche),
                              coupe_gauche=debut < lundi, coupe_droite=fin > dimanche))
    visibles.sort(key=lambda b: (b.debut, -(b.fin - b.debut).days, b.cle))
    fins_pistes: list[date] = []
    for bande in visibles:
        for i, fin in enumerate(fins_pistes):
            if fin < bande.debut:
                bande.piste, fins_pistes[i] = i, bande.fin
                break
        else:
            bande.piste = len(fins_pistes)
            fins_pistes.append(bande.fin)
    return visibles


def colonnes(intervalles: list[tuple[str, datetime, datetime]]) -> dict[str, tuple[int, int]]:
    """Vue semaine : cle -> (colonne, nombre de colonnes du groupe qui se chevauche)."""
    resultat: dict[str, tuple[int, int]] = {}
    groupe: list[tuple[str, int]] = []
    fins_colonnes: list[datetime] = []
    fin_groupe = None

    def clore():
        for cle, col in groupe:
            resultat[cle] = (col, len(fins_colonnes))

    for cle, debut, fin in sorted(intervalles, key=lambda x: (x[1], x[2])):
        fin = max(fin, debut + timedelta(minutes=30))
        if fin_groupe is not None and debut >= fin_groupe:
            clore()
            groupe, fins_colonnes, fin_groupe = [], [], None
        for i, f in enumerate(fins_colonnes):
            if f <= debut:
                col, fins_colonnes[i] = i, fin
                break
        else:
            col = len(fins_colonnes)
            fins_colonnes.append(fin)
        groupe.append((cle, col))
        fin_groupe = fin if fin_groupe is None else max(fin_groupe, fin)
    clore()
    return resultat
