"""Récupération de la programmation du BLMK (https://www.blmk.de/kalender/).

Le site tourne sous WordPress + « The Events Calendar » (Pro). Deux sources :

1. L'API REST du plugin (`/wp-json/tribe/events/v1/events`) : données propres,
   dates/heures complètes. On demande `ends_after=maintenant` pour inclure les
   expositions déjà ouvertes (c'est exactement ce qu'affiche /kalender/).
2. La page /kalender/ : elle contient un bloc JSON-LD (schema.org/Event) avec le
   statut (`EventScheduled`, `EventCancelled`, `EventPostponed`…), absent de l'API.
   Elle sert aussi de solution de secours si l'API ne répond pas.

Identifiant stable : le chemin de l'URL de la fiche (ex.
`programm/ferienkurs-manga/2026-10-29`). Les identifiants numériques diffèrent
entre l'API et la page HTML pour les occurrences d'événements récurrents.
"""

from __future__ import annotations

import html
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import config

LONGUEUR_DESCRIPTION = 400


@dataclass
class Evenement:
    uid: str
    title: str
    kicker: str
    type: str
    start: str  # "AAAA-MM-JJTHH:MM", heure locale de Berlin
    end: str
    all_day: bool
    venue: str
    address: str
    city: str
    description: str
    url: str
    image: str = ""
    status: str = "prevu"  # prevu / annule / reporte
    categories: list[str] = field(default_factory=list)
    source_id: int | None = None

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Petits utilitaires de nettoyage
# --------------------------------------------------------------------------

def uid_depuis_url(url: str) -> str:
    return urlparse(url).path.strip("/")


def texte_brut(fragment: str) -> str:
    """HTML -> texte simple, espaces normalisés."""
    if not fragment:
        return ""
    texte = BeautifulSoup(html.unescape(fragment), "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", texte).strip()


def raccourcir(texte: str, n: int = LONGUEUR_DESCRIPTION) -> str:
    if len(texte) <= n:
        return texte
    coupe = texte[:n].rsplit(" ", 1)[0]
    return coupe.rstrip(" ,;:") + "…"


def separer_titre(titre_html: str) -> tuple[str, str]:
    """'<b>Führung</b> in „Fons Hickmann…“' -> ('Führung – in „Fons Hickmann…“', 'Führung').

    Sur le site, la partie en gras est un sur-titre (type d'activité ou artiste).
    """
    soupe = BeautifulSoup(html.unescape(titre_html or ""), "html.parser")
    gras = soupe.find(["b", "strong"])
    kicker = re.sub(r"\s+", " ", gras.get_text(" ")).strip() if gras else ""
    if gras:
        gras.extract()
    reste = re.sub(r"\s+", " ", soupe.get_text(" ")).strip()
    if kicker and reste:
        return f"{kicker} – {reste}", kicker
    return kicker or reste, kicker


def date_locale(valeur: str) -> str:
    """'2026-10-28 10:00:00' ou '2026-09-27T11:00:00+02:00' -> '2026-10-28T10:00'.

    Les décalages présents sont déjà ceux de Berlin : on garde l'heure locale.
    """
    if not valeur:
        return ""
    dt = datetime.fromisoformat(valeur.replace(" ", "T"))
    return dt.replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M")


_TYPES = [  # ordre = priorité
    ("exposition", ("ausstellung",)),
    ("vernissage", ("eroeffnung", "eröffnung")),
    ("visite", ("fuehrung", "führung")),
    ("concert", ("konzert",)),
    ("atelier", ("workshop", "atelier", "abendkurs", "kreativwerkstatt", "ferienprogramm")),
    ("evenement", ("sonderveranstaltung",)),
    ("annonce", ("ankuendigung", "ankündigung")),
]


def type_depuis_categories(categories: list[str]) -> str:
    noms = [c.lower() for c in categories]
    for type_, motifs in _TYPES:
        if any(m in nom for nom in noms for m in motifs):
            return type_
    return "autre"


def ville_depuis_categories(categories: list[str]) -> str:
    noms = " ".join(c.lower() for c in categories)
    if "frankfurt" in noms:
        return "Frankfurt (Oder)"
    if "cottbus" in noms:
        return "Cottbus"
    return ""


_STATUTS_SCHEMA = {
    "EventScheduled": "prevu",
    "EventRescheduled": "prevu",
    "EventMovedOnline": "prevu",
    "EventCancelled": "annule",
    "EventPostponed": "reporte",
}


def statut_depuis_titre(titre: str) -> str | None:
    t = titre.lower()
    if re.search(r"\b(abgesagt|entfällt|fällt aus|annulé)\b", t):
        return "annule"
    if re.search(r"\b(verschoben|reporté)\b", t):
        return "reporte"
    return None


# --------------------------------------------------------------------------
# Parsing : API REST
# --------------------------------------------------------------------------

def parser_evenement_api(e: dict) -> Evenement | None:
    if e.get("hide_from_listings"):
        return None
    categories = [c.get("slug") or c.get("name", "") for c in e.get("categories") or []]
    titre, kicker = separer_titre(e.get("title", ""))
    venue = e.get("venue") or {}
    if isinstance(venue, list):  # le plugin renvoie [] quand il n'y a pas de lieu
        venue = venue[0] if venue else {}
    description = texte_brut(e.get("excerpt") or "") or texte_brut(e.get("description") or "")
    image = e.get("image") or {}
    return Evenement(
        uid=uid_depuis_url(e["url"]),
        title=titre,
        kicker=kicker,
        type=type_depuis_categories(categories),
        start=date_locale(e.get("start_date", "")),
        end=date_locale(e.get("end_date", "")),
        all_day=bool(e.get("all_day")),
        venue=html.unescape(venue.get("venue", "") or ""),
        address=html.unescape(venue.get("address", "") or ""),
        city=html.unescape(venue.get("city", "") or "") or ville_depuis_categories(categories),
        description=raccourcir(description),
        url=e["url"],
        image=image.get("url", "") if isinstance(image, dict) else "",
        status=statut_depuis_titre(titre) or "prevu",
        categories=categories,
        source_id=e.get("id"),
    )


def parser_page_api(donnees: dict) -> list[Evenement]:
    return [ev for ev in (parser_evenement_api(e) for e in donnees.get("events", [])) if ev]


# --------------------------------------------------------------------------
# Parsing : page HTML /kalender/
# --------------------------------------------------------------------------

def _jsonld_evenements(soupe: BeautifulSoup) -> list[dict]:
    resultat = []
    for script in soupe.find_all("script", type="application/ld+json"):
        try:
            donnees = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        for item in donnees if isinstance(donnees, list) else [donnees]:
            if isinstance(item, dict) and item.get("@type") == "Event":
                resultat.append(item)
    return resultat


def statuts_depuis_html(page_html: str) -> dict[str, str]:
    """uid -> statut, lu dans le JSON-LD de la page calendrier."""
    soupe = BeautifulSoup(page_html, "html.parser")
    statuts = {}
    for item in _jsonld_evenements(soupe):
        brut = (item.get("eventStatus") or "").rsplit("/", 1)[-1]
        if item.get("url") and brut:
            statuts[uid_depuis_url(item["url"])] = _STATUTS_SCHEMA.get(brut, "prevu")
    return statuts


def parser_html(page_html: str) -> list[Evenement]:
    """Événements d'une page /kalender/ : JSON-LD + blocs de la liste."""
    soupe = BeautifulSoup(page_html, "html.parser")

    blocs = {}
    for bloc in soupe.select("div.type-tribe_events"):
        lien = bloc.select_one("a.tribe-event-url")
        if not lien:
            continue
        classes = bloc.get("class", [])
        categories = [c.removeprefix("tribe-events-category-") for c in classes
                      if c.startswith("tribe-events-category-")]
        texte = bloc.select_one(".post__content-text-inner")
        if texte:
            texte = BeautifulSoup(str(texte), "html.parser")
            for parasite in texte.select(".post__content-venue, .post__content-buttons"):
                parasite.decompose()
        post_id = re.match(r"post-(\d+)", bloc.get("id", ""))
        blocs[uid_depuis_url(lien["href"])] = {
            "categories": categories,
            "description": re.sub(r"\s+", " ", texte.get_text(" ")).strip() if texte else "",
            "id": int(post_id.group(1)) if post_id else None,
        }

    evenements = []
    for item in _jsonld_evenements(soupe):
        url = item.get("url")
        if not url:
            continue
        uid = uid_depuis_url(url)
        bloc = blocs.get(uid, {})
        categories = bloc.get("categories", [])
        titre, kicker = separer_titre(item.get("name", ""))
        lieu = item.get("location") or {}
        adresse = lieu.get("address") or {}
        if isinstance(adresse, str):
            adresse = {"streetAddress": adresse}
        statut = _STATUTS_SCHEMA.get((item.get("eventStatus") or "").rsplit("/", 1)[-1], "prevu")
        description = bloc.get("description") or texte_brut(item.get("description", ""))
        evenements.append(Evenement(
            uid=uid,
            title=titre,
            kicker=kicker,
            type=type_depuis_categories(categories),
            start=date_locale(item.get("startDate", "")),
            end=date_locale(item.get("endDate", "")),
            all_day=False,
            venue=html.unescape(lieu.get("name", "") or ""),
            address=html.unescape(adresse.get("streetAddress", "") or ""),
            city=html.unescape(adresse.get("addressLocality", "") or "") or ville_depuis_categories(categories),
            description=raccourcir(description),
            url=url,
            image=item.get("image", "") if isinstance(item.get("image"), str) else "",
            status=statut if statut != "prevu" else (statut_depuis_titre(titre) or "prevu"),
            categories=categories,
            source_id=bloc.get("id"),
        ))
    return evenements


def lien_page_suivante(page_html: str, url_courante: str) -> str | None:
    soupe = BeautifulSoup(page_html, "html.parser")
    lien = soupe.select_one("a[rel=next], a.tribe-events-c-nav__next, .tribe-events-nav-next a")
    if lien and lien.get("href"):
        suivante = urljoin(url_courante, lien["href"])
        return suivante if suivante != url_courante else None
    return None


# --------------------------------------------------------------------------
# Téléchargement (poli : une requête à la fois, petit délai)
# --------------------------------------------------------------------------

class Client:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self._derniere = 0.0

    def get(self, url: str, **params) -> requests.Response:
        attente = config.DELAI_ENTRE_REQUETES - (time.monotonic() - self._derniere)
        if attente > 0:
            time.sleep(attente)
        try:
            reponse = self.session.get(url, params=params or None, timeout=config.TIMEOUT)
        finally:
            self._derniere = time.monotonic()
        reponse.raise_for_status()
        return reponse


def recuperer_api(client: Client, maintenant: datetime | None = None) -> list[Evenement]:
    maintenant = maintenant or datetime.now()
    evenements: list[Evenement] = []
    page = 1
    while page <= config.MAX_PAGES:
        donnees = client.get(
            config.URL_API,
            per_page=config.PAR_PAGE,
            page=page,
            ends_after=maintenant.strftime("%Y-%m-%d %H:%M:%S"),
        ).json()
        evenements += parser_page_api(donnees)
        if page >= int(donnees.get("total_pages") or 1):
            break
        page += 1
    return evenements


def recuperer_pages_html(client: Client) -> list[str]:
    pages, url = [], config.URL_CALENDRIER
    while url and len(pages) < config.MAX_PAGES:
        texte = client.get(url).text
        pages.append(texte)
        url = lien_page_suivante(texte, url)
    return pages


def dedoublonner(evenements: list[Evenement]) -> list[Evenement]:
    vus: dict[str, Evenement] = {}
    for ev in evenements:
        vus.setdefault(ev.uid, ev)
    return list(vus.values())


def recuperer_programmation(client: Client | None = None) -> tuple[list[Evenement], str, str | None]:
    """Renvoie (événements, source utilisée 'api' ou 'html', erreur API éventuelle).

    Lève une exception seulement si aucune des deux sources ne fonctionne.
    """
    client = client or Client()
    erreur_api = None
    try:
        evenements = recuperer_api(client)
    except (requests.RequestException, ValueError, KeyError) as exc:
        evenements, erreur_api = [], str(exc)

    try:
        pages = recuperer_pages_html(client)
    except requests.RequestException:
        if erreur_api:
            raise
        pages = []  # on garde l'API, sans les statuts du JSON-LD

    if erreur_api is None and evenements:
        statuts = {}
        for page in pages:
            statuts.update(statuts_depuis_html(page))
        for ev in evenements:
            if statuts.get(ev.uid, "prevu") != "prevu":
                ev.status = statuts[ev.uid]
        return dedoublonner(evenements), "api", None

    evenements = [ev for page in pages for ev in parser_html(page)]
    return dedoublonner(evenements), "html", erreur_api or "réponse vide"
