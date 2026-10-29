"""Mises à jour : versions, choix du paquet, empreintes, emplacement, préparation."""

import hashlib
import zipfile

import pytest

from musee_zoune import config, maj
from musee_zoune.maj import Fichier, Release


def release(version="1.3", noms=(), notes=""):
    fichiers = {n: Fichier(n, f"http://exemple/{n}", 1000) for n in noms}
    return Release(version, notes, "http://exemple/page", fichiers)


def avec_empreintes(*noms):
    return [x for n in noms for x in (n, n + ".sha256")]


# ---------------------------------------------------------------------- versions

@pytest.mark.parametrize("a, b, attendu", [
    ("1.2", "1.1", True), ("v1.10", "1.9", True), ("1.2", "1.2.0", False), ("1.2.1", "1.2", True),
    ("2.0", "1.99", True), ("1.1", "1.2", False), ("1.2", "1.2-beta", True), ("1.2-beta", "1.1", True),
])
def test_comparaison_de_versions(a, b, attendu):
    assert maj.plus_recente(a, b) is attendu


def test_version_illisible():
    with pytest.raises(ValueError):
        maj.version_tuple("dernière")


def test_lire_release_github():
    r = maj.lire_release({"tag_name": "v1.3", "body": "notes", "html_url": "http://page", "assets": [
        {"name": "a.zip", "browser_download_url": "http://a", "size": 12}]})
    assert (r.version, r.page, r.fichiers["a.zip"].taille) == ("1.3", "http://page", 12)


# ---------------------------------------------------------------------- choix du paquet

def test_mise_a_jour_legere_si_base_compatible():
    r = release(noms=avec_empreintes("MuseeZoune-1.3-windows.zip", "MuseeZoune-1.3-maj-depuis-1.0.zip"))
    for installee in ("1.0", "1.1", "1.2"):
        choix = maj.choisir_paquet(r, installee)
        assert choix.mode == "fichiers" and choix.archive.nom == "MuseeZoune-1.3-maj-depuis-1.0.zip"
        assert choix.empreinte.nom == "MuseeZoune-1.3-maj-depuis-1.0.zip.sha256"


def test_installation_complete_si_version_trop_ancienne():
    r = release(noms=avec_empreintes("MuseeZoune-1.3-windows.zip", "MuseeZoune-1.3-maj-depuis-1.2.zip"))
    choix = maj.choisir_paquet(r, "1.1")
    assert choix.mode == "dossier" and choix.archive.nom == "MuseeZoune-1.3-windows.zip"


def test_marqueur_impose_installation_complete():
    r = release(noms=avec_empreintes("MuseeZoune-1.3-windows.zip", "MuseeZoune-1.3-maj-depuis-1.0.zip"),
                notes=f"Nouveautés\n{maj.MARQUEUR_COMPLETE}\n")
    assert maj.choisir_paquet(r, "1.2").mode == "dossier"
    assert maj.MARQUEUR_COMPLETE not in r.notes_affichables()


def test_la_base_la_plus_proche_est_choisie():
    r = release(noms=avec_empreintes("MuseeZoune-1.3-maj-depuis-1.0.zip", "MuseeZoune-1.3-maj-depuis-1.2.zip"))
    assert maj.choisir_paquet(r, "1.2").archive.nom == "MuseeZoune-1.3-maj-depuis-1.2.zip"
    assert maj.choisir_paquet(r, "1.1").archive.nom == "MuseeZoune-1.3-maj-depuis-1.0.zip"


def test_pas_de_paquet_sans_empreinte_ou_sans_nouvelle_version():
    sans_empreinte = release(noms=("MuseeZoune-1.3-windows.zip", "MuseeZoune-1.3-maj-depuis-1.0.zip"))
    assert maj.choisir_paquet(sans_empreinte, "1.2") is None
    autre_version = release(noms=avec_empreintes("MuseeZoune-1.2-maj-depuis-1.0.zip"))
    assert maj.choisir_paquet(autre_version, "1.2") is None
    assert maj.choisir_paquet(release("1.2", avec_empreintes("MuseeZoune-1.2-windows.zip")), "1.2") is None


# ---------------------------------------------------------------------- empreintes

def test_lire_et_verifier_empreinte(tmp_path):
    f = tmp_path / "a.zip"
    f.write_bytes(b"contenu")
    h = hashlib.sha256(b"contenu").hexdigest()
    assert maj.lire_empreinte(f"{h.upper()}  a.zip\n") == h
    assert maj.lire_empreinte(h) == h
    maj.verifier_empreinte(f, h)
    with pytest.raises(maj.ErreurMaj):
        maj.verifier_empreinte(f, "0" * 64)
    with pytest.raises(maj.ErreurMaj):
        maj.lire_empreinte("<html>Not Found</html>")


# ---------------------------------------------------------------------- emplacement et archive

def application(tmp_path, contenu=b"exe 1.2"):
    dossier = tmp_path / "Programmes" / "Musee Zoune"
    (dossier / "_internal").mkdir(parents=True)
    (dossier / maj.NOM_EXE).write_bytes(contenu)
    (dossier / "_internal" / "lib.dll").write_bytes(b"lib 1.2")
    return dossier


def test_emplacement_refuse_le_dossier_des_donnees(tmp_path, monkeypatch):
    app = application(tmp_path)
    monkeypatch.setattr(config, "DOSSIER_DONNEES", tmp_path / "donnees")
    maj.verifier_emplacement(app)
    monkeypatch.setattr(config, "DOSSIER_DONNEES", app / "data")
    with pytest.raises(maj.ErreurMaj):
        maj.verifier_emplacement(app)
    monkeypatch.setattr(config, "DOSSIER_DONNEES", app.parent)
    with pytest.raises(maj.ErreurMaj):
        maj.verifier_emplacement(app)


def test_archive_avec_chemin_dangereux_refusee(tmp_path):
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("racine/Musee Zoune/../../evade.txt", "x")
    with pytest.raises(maj.ErreurMaj):
        maj.extraire_application(archive, tmp_path / "sortie")
    assert not (tmp_path / "evade.txt").exists()


def test_extraction_garde_seulement_l_application(tmp_path):
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("racine/Musee Zoune/Musee Zoune.exe", "exe")
        z.writestr("racine/Musee Zoune/_internal/lib.dll", "lib")
        z.writestr("racine/source/README.md", "source")
        z.writestr("racine/LISEZMOI.txt", "lisez-moi")
    assert sorted(maj.extraire_application(archive, tmp_path / "s")) == ["Musee Zoune.exe", "_internal/lib.dll"]


class FausseReponse:
    def __init__(self, contenu: bytes):
        self.contenu, self.text = contenu, contenu.decode("latin-1")

    def raise_for_status(self):
        pass

    def iter_content(self, _taille):
        yield self.contenu

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FausseSession:
    def __init__(self, fichiers: dict[str, bytes]):
        self.fichiers = fichiers

    def get(self, url, **_):
        return FausseReponse(self.fichiers[url.rsplit("/", 1)[1]])


def zip_maj(exe: bytes) -> bytes:
    import io
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("MuseeZoune-1.3-maj-depuis-1.0/Musee Zoune/Musee Zoune.exe", exe)
    return tampon.getvalue()


def test_preparation_puis_empreinte_fausse_ne_touche_a_rien(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DOSSIER_DONNEES", tmp_path / "donnees")
    app = application(tmp_path)
    nom = "MuseeZoune-1.3-maj-depuis-1.0.zip"
    contenu = zip_maj(b"exe 1.3")
    r = release(noms=avec_empreintes(nom))
    choix = maj.choisir_paquet(r, "1.2")

    bonne = FausseSession({nom: contenu, nom + ".sha256": f"{hashlib.sha256(contenu).hexdigest()}  {nom}".encode()})
    attente = maj.preparer(r, choix, app, session=bonne)
    assert (attente / "maj.json").exists()
    assert (attente / "fichiers" / maj.NOM_EXE).read_bytes() == b"exe 1.3"
    assert not (attente / "telechargement").exists()

    fausse = FausseSession({nom: contenu, nom + ".sha256": ("0" * 64).encode()})
    with pytest.raises(maj.ErreurMaj):
        maj.preparer(r, choix, app, session=fausse)
    assert not maj.dossier_attente(app).exists()
    assert (app / maj.NOM_EXE).read_bytes() == b"exe 1.2"


def test_installation_complete_doit_contenir_les_bibliotheques(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DOSSIER_DONNEES", tmp_path / "donnees")
    app = application(tmp_path)
    nom = "MuseeZoune-1.3-windows.zip"
    contenu = zip_maj(b"exe seul")
    r = release(noms=avec_empreintes(nom))
    session = FausseSession({nom: contenu, nom + ".sha256": hashlib.sha256(contenu).hexdigest().encode()})
    with pytest.raises(maj.ErreurMaj):
        maj.preparer(r, maj.choisir_paquet(r, "1.2"), app, session=session)
    assert not maj.dossier_attente(app).exists()


def test_nettoyage_des_restes(tmp_path):
    app = application(tmp_path)
    (app / "Musee Zoune.exe.old").write_bytes(b"ancien")
    (app.parent / "Musee Zoune.ancien").mkdir()
    maj.nettoyer(app)
    assert not (app / "Musee Zoune.exe.old").exists() and not (app.parent / "Musee Zoune.ancien").exists()
    assert (app / maj.NOM_EXE).exists()


def test_mode_developpement_n_installe_rien(monkeypatch):
    monkeypatch.delattr("sys.frozen", raising=False)
    assert config.est_installee() is False
    assert maj.appliquer_en_attente() is False


def test_mise_a_jour_en_attente_appliquee_au_lancement(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DOSSIER_DONNEES", tmp_path / "donnees")
    app = application(tmp_path)
    attente = maj.dossier_attente(app)
    attente.mkdir()
    (attente / "maj.json").write_text('{"mode": "fichiers"}', encoding="utf-8")
    appels = []
    monkeypatch.setattr(config, "est_installee", lambda: True)
    monkeypatch.setattr("sys.executable", str(app / maj.NOM_EXE))
    monkeypatch.setattr(maj, "lancer_application", lambda *a, **k: appels.append((a, k)))
    assert maj.appliquer_en_attente() is True
    assert appels and appels[0][1]["relancer"] is True
