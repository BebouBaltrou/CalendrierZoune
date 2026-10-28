"""Tests du parsing, à partir de pages sauvegardées le 28/10/2026."""

import json
from pathlib import Path

import pytest

from musee_zoune.scraper import (
    date_locale,
    lien_page_suivante,
    parser_html,
    parser_page_api,
    separer_titre,
    statuts_depuis_html,
    type_depuis_categories,
    uid_depuis_url,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def page_html() -> str:
    return (FIXTURES / "kalender.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def evenements_html(page_html):
    return {ev.uid: ev for ev in parser_html(page_html)}


@pytest.fixture(scope="module")
def evenements_api():
    resultat = {}
    for nom in ("api_page1.json", "api_page2.json"):
        donnees = json.loads((FIXTURES / nom).read_text(encoding="utf-8"))
        resultat.update({ev.uid: ev for ev in parser_page_api(donnees)})
    return resultat


# --- Page HTML -------------------------------------------------------------

def test_html_tous_les_evenements(evenements_html):
    assert len(evenements_html) == 62


def test_html_exposition_avec_periode(evenements_html):
    ev = evenements_html["programm/fons-hickmann"]
    assert ev.type == "exposition"
    assert ev.kicker == "Fons Hickmann"
    assert ev.title == "Fons Hickmann – Plakate von heute und davor"
    assert ev.start == "2026-10-03T11:00"
    assert ev.end == "2026-12-06T19:00"
    assert ev.city == "Cottbus"


def test_html_occurrence_recurrente_identifiant_avec_date(evenements_html):
    ev = evenements_html["programm/ferienkurs-manga-bewegung-und-kleidung/2026-10-29"]
    assert ev.type == "atelier"
    assert ev.start == "2026-10-29T10:00"
    assert ev.end == "2026-10-29T12:00"
    assert ev.venue == "Dieselkraftwerk"


def test_html_description_sans_boutons_ni_adresse(evenements_html):
    for ev in evenements_html.values():
        assert "Termin speichern" not in ev.description
        assert "Permalink" not in ev.description
        assert len(ev.description) <= 401


def test_html_champs_obligatoires(evenements_html):
    for ev in evenements_html.values():
        assert ev.title and ev.start and ev.url.startswith("https://www.blmk.de/")
        assert ev.end >= ev.start
        assert ev.status == "prevu"
        assert ev.type != "autre"


def test_html_statut_annule_lu_dans_jsonld(page_html):
    modifiee = page_html.replace(
        "https://schema.org/EventScheduled", "https://schema.org/EventCancelled", 1
    )
    annules = [ev for ev in parser_html(modifiee) if ev.status == "annule"]
    assert len(annules) == 1
    assert statuts_depuis_html(modifiee)[annules[0].uid] == "annule"


def test_html_pas_de_page_suivante(page_html):
    assert lien_page_suivante(page_html, "https://www.blmk.de/kalender/") is None


# --- API ------------------------------------------------------------------

def test_api_meme_evenements_que_la_page(evenements_api, evenements_html):
    assert set(evenements_api) == set(evenements_html)


@pytest.mark.parametrize("champ", ["title", "type", "start", "end", "venue", "city", "url"])
def test_api_et_html_concordent(evenements_api, evenements_html, champ):
    ecarts = [uid for uid, ev in evenements_api.items()
              if getattr(ev, champ) != getattr(evenements_html[uid], champ)]
    assert ecarts == []


def test_api_evenement_sans_lieu_ville_deduite():
    ev = parser_page_api({"events": [{
        "id": 1, "url": "https://www.blmk.de/programm/test/", "title": "<b>Test</b> Sans lieu",
        "start_date": "2026-11-01 10:00:00", "end_date": "2026-11-01 11:00:00",
        "venue": [], "categories": [{"slug": "frankfurt-oder", "name": "Frankfurt (Oder)"}],
        "excerpt": "", "description": "<p>Texte</p>", "image": False,
    }]})[0]
    assert ev.city == "Frankfurt (Oder)"
    assert ev.venue == ""
    assert ev.description == "Texte"
    assert ev.image == ""


def test_api_titre_abgesagt_donne_annule():
    ev = parser_page_api({"events": [{
        "id": 2, "url": "https://www.blmk.de/programm/x/", "title": "<b>Abgesagt:</b> Führung",
        "start_date": "2026-11-01 10:00:00", "end_date": "2026-11-01 11:00:00",
        "venue": {}, "categories": [], "excerpt": "", "description": "", "image": {},
    }]})[0]
    assert ev.status == "annule"


# --- Utilitaires ------------------------------------------------------------

def test_separer_titre():
    assert separer_titre("<b>Führung</b> in &#8222;Fons&#8220;") == ("Führung – in „Fons“", "Führung")
    assert separer_titre("Kunstpreis 2026") == ("Kunstpreis 2026", "")


def test_date_locale():
    assert date_locale("2026-10-28 10:00:00") == "2026-10-28T10:00"
    assert date_locale("2026-11-22T17:00:00+01:00") == "2026-11-22T17:00"


def test_types():
    assert type_depuis_categories(["ausstellung", "cottbus"]) == "exposition"
    assert type_depuis_categories(["fuehrung", "kunstvermittlung"]) == "visite"
    assert type_depuis_categories(["workshops", "atelier-cottbus"]) == "atelier"
    assert type_depuis_categories(["stadt"]) == "autre"


def test_uid():
    assert uid_depuis_url("https://www.blmk.de/programm/a/2026-10-29/") == "programm/a/2026-10-29"
