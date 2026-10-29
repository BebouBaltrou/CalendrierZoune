"""Fenêtre « Paramètres » : réglage des mises à jour mémorisé, textes FR/DE."""

import pytest

from musee_zoune import db, maj, textes


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn():
    c = db.connecter(":memory:")
    yield c
    c.close()


@pytest.mark.parametrize("langue", ["fr", "de"])
def test_reglage_des_mises_a_jour(app, conn, langue):
    from PySide6.QtWidgets import QWidget

    from musee_zoune.app.parametres import DialogueParametres, GestionMaj
    textes.choisir_langue(langue)
    try:
        hote = QWidget()
        gestion = GestionMaj(hote, conn)
        assert gestion.mode() == "auto"  # par défaut
        dlg = DialogueParametres(gestion, hote)
        assert dlg.radio_auto.isChecked()
        assert textes.t("maj_jamais") in dlg.lbl_derniere.text()
        assert textes.t("maj_dev") and dlg.btn_rechercher.isEnabled()

        dlg.radio_manuel.setChecked(True)
        assert db.lire_reglage(conn, "maj_mode") == "manuel"
        assert GestionMaj(hote, conn).mode() == "manuel"
        assert DialogueParametres(gestion, hote).radio_manuel.isChecked()

        db.ecrire_reglage(conn, "maj_derniere_verif", "2026-10-29T21:50:00")
        dlg.rafraichir()
        assert "29/10/2026 21:50" in dlg.lbl_derniere.text()
    finally:
        textes.choisir_langue("fr")


def test_mode_manuel_ne_verifie_pas_au_lancement(app, conn, monkeypatch):
    from PySide6.QtWidgets import QWidget

    from musee_zoune.app.parametres import GestionMaj
    appels = []
    monkeypatch.setattr("musee_zoune.app.parametres.QTimer.singleShot", lambda *a: appels.append(a))
    gestion = GestionMaj(QWidget(), conn)
    gestion.choisir_mode("manuel")
    gestion.demarrage()
    assert appels == []
    gestion.choisir_mode("auto")
    gestion.demarrage()
    assert len(appels) == 1


def test_auto_installe_sans_question_seulement_si_exe(app, conn, monkeypatch):
    from PySide6.QtWidgets import QWidget

    from musee_zoune.app.parametres import GestionMaj
    gestion = GestionMaj(QWidget(), conn)
    installs = []
    monkeypatch.setattr(gestion, "installer", lambda *a, **k: installs.append(a))
    r = maj.Release("9.0", "", "", {n: maj.Fichier(n, "http://x/" + n) for n in
                                    ("MuseeZoune-9.0-windows.zip", "MuseeZoune-9.0-windows.zip.sha256")})
    gestion._verifiee(r, silencieux=True)       # version de développement : rien
    assert installs == [] and db.lire_reglage(conn, "maj_derniere_verif")
    monkeypatch.setattr("musee_zoune.config.est_installee", lambda: True)
    gestion._verifiee(r, silencieux=True)
    assert len(installs) == 1
