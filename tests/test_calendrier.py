"""Couleurs des expositions, liens expo, mise en page."""

from datetime import date, datetime
from pathlib import Path

import pytest

from musee_zoune import calendrier as cal
from musee_zoune import db
from musee_zoune.app.donnees import Donnees
from musee_zoune.scraper import parser_html
from musee_zoune.sync import synchroniser

FIXTURES = Path(__file__).parent / "fixtures"


def expo(uid, debut, fin, kicker="", city="Cottbus"):
    return {"uid": uid, "start": debut + "T11:00", "end": fin + "T18:00", "type": "exposition",
            "kicker": kicker or uid, "title": kicker or uid, "city": city}


@pytest.fixture(scope="module")
def base():
    conn = db.connecter(":memory:")
    evs = parser_html((FIXTURES / "kalender.html").read_text(encoding="utf-8"))
    synchroniser(conn, evs, "html", datetime(2026, 10, 28, 21, 0))
    yield conn
    conn.close()


# --- Couleurs -------------------------------------------------------------

def test_expos_simultanees_couleurs_differentes():
    expos = [expo(f"e{i}", "2026-10-01", "2026-12-01") for i in range(10)]
    couleurs = cal.attribuer_couleurs(expos, {})
    assert len(set(couleurs.values())) == 10


def test_couleur_existante_jamais_modifiee():
    expos = [expo("a", "2026-10-01", "2026-12-01"), expo("b", "2026-10-01", "2026-12-01")]
    nouvelles = cal.attribuer_couleurs(expos, {"a": 5})
    assert nouvelles == {"b": 0}  # « a » garde 5 et n'est pas renvoyée


def test_nouvelle_expo_evite_les_couleurs_en_cours():
    existantes = {"a": 0, "b": 1}
    expos = [expo("a", "2026-10-01", "2026-12-01"), expo("b", "2026-11-01", "2026-12-31"),
             expo("c", "2026-11-15", "2027-01-15")]
    assert cal.attribuer_couleurs(expos, existantes)["c"] not in (0, 1)


def test_couleurs_stables_entre_deux_chargements(base):
    premiere = Donnees(base).couleurs
    seconde = Donnees(base).couleurs
    assert premiere == seconde and len(premiere) == 12
    assert len(set(premiere.values())) == 12  # 12 expos, 14 couleurs : toutes distinctes


def test_plus_d_expos_que_de_couleurs():
    expos = [expo(f"e{i:02d}", "2026-10-01", "2026-12-01") for i in range(20)]
    couleurs = cal.attribuer_couleurs(expos, {})
    assert len(couleurs) == 20 and set(couleurs.values()) == set(range(len(cal.PALETTE)))


# --- Liens visites / vernissages -> exposition ------------------------------

def test_visites_et_vernissages_lies(base):
    d = Donnees(base)
    titres = {e["uid"]: e["title"] for e in db.evenements_entre(base, "0", "9")}
    lies = {titres[u]: titres[x] for u, x in d.liens.items()}
    assert lies["Führung – in „Fons Hickmann. Plakate von heute und davor“"].startswith("Fons Hickmann")
    vernissages = [v for k, v in lies.items() if k.startswith("Ausstellungseröffnung")]
    assert len(vernissages) == 3
    assert not any(k.startswith("Ferienkurs") for k in lies)  # ateliers sans exposition


def test_evenement_lie_prend_la_couleur_de_l_expo(base):
    d = Donnees(base)
    evs = {e["uid"]: e for e in db.evenements_entre(base, "0", "9")}
    assert d.liens
    for uid, expo_uid in d.liens.items():
        assert cal.couleur_evenement(evs[uid], d.liens, d.couleurs) == d.couleur_expo(expo_uid)


def test_lien_hors_periode_refuse():
    expos = [expo("fons", "2026-10-03", "2026-12-06", kicker="Fons Hickmann")]
    ev = {"uid": "v", "type": "visite", "start": "2027-03-01T10:00", "city": "Cottbus",
          "title": "Führung – in „Fons Hickmann. Plakate“"}
    assert cal.lier_aux_expositions([ev], expos) == {}


# --- Mise en page --------------------------------------------------------------

def test_bandes_sur_pistes_distinctes():
    lundi = date(2026, 11, 2)
    bandes = cal.bandes_semaine([("a", date(2026, 10, 1), date(2026, 12, 1)),
                                 ("b", date(2026, 11, 3), date(2026, 11, 4)),
                                 ("c", date(2026, 11, 5), date(2026, 11, 20))], lundi)
    pistes = {b.cle: b.piste for b in bandes}
    assert pistes["a"] != pistes["b"]
    assert pistes["b"] == pistes["c"]  # se suivent : même piste
    a = next(b for b in bandes if b.cle == "a")
    assert a.coupe_gauche and a.coupe_droite and a.debut == lundi


def test_colonnes_chevauchement():
    def h(hh, mm=0):
        return datetime(2026, 11, 5, hh, mm)
    places = cal.colonnes([("a", h(11), h(12)), ("b", h(11, 30), h(12, 30)), ("c", h(14), h(15))])
    assert places["a"] == (0, 2) and places["b"] == (1, 2) and places["c"] == (0, 1)


def test_semaines_du_mois():
    lundis = cal.semaines_du_mois(2026, 11)
    assert lundis[0] == date(2026, 10, 26) and len(lundis) == 6


def test_fin_a_minuit_compte_la_veille():
    assert cal.jours_de({"start": "2026-11-01T10:00", "end": "2026-11-03T00:00"}) == (
        date(2026, 11, 1), date(2026, 11, 2))


# --- Mode compact de la vue mois ------------------------------------------------

def test_compact_huit_expos_le_mois_tient_a_l_ecran():
    from musee_zoune.app.vue_mois import disposition_semaine
    zone, semaines = 780, 6
    h_cible = (zone - 26) / semaines
    hauteur, lignes = disposition_semaine(0, 8, 5, compact=True, h_cible=h_cible)
    assert hauteur * semaines <= zone - 24
    assert lignes >= 3  # au moins 3 lignes de pastilles (ou 2 + « +n autres »)


def test_normal_les_bandes_prennent_de_la_place():
    from musee_zoune.app.vue_mois import H_BANDE, disposition_semaine
    hauteur, _ = disposition_semaine(0, 8, 5, compact=False)
    assert hauteur > 8 * H_BANDE


def test_compact_vie_perso_garde_sa_hauteur():
    from musee_zoune.app.vue_mois import H_BANDE, H_FINE, disposition_semaine
    h1, l1 = disposition_semaine(1, 8, 9, compact=True, h_cible=200)
    h0, l0 = disposition_semaine(0, 8, 9, compact=True, h_cible=200)
    assert h1 == h0 == 200 and l1 <= l0
    assert H_FINE < H_BANDE
