"""Bout en bout : faux serveur local de releases GitHub, téléchargement, vérification,
puis application par le vrai script PowerShell (échange, retour arrière, attente)."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from musee_zoune import config, maj

pytestmark = pytest.mark.skipif(os.name != "nt" or not shutil.which("powershell.exe"),
                                reason="script de mise à jour Windows (PowerShell)")


class Silencieux(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


@pytest.fixture
def serveur(tmp_path):
    """Sert tmp_path/web : /api/latest (JSON façon GitHub) et /files/<asset>."""
    racine = tmp_path / "web"
    (racine / "files").mkdir(parents=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(Silencieux, directory=str(racine)))
    fil = threading.Thread(target=httpd.serve_forever, daemon=True)
    fil.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def publier(version: str, paquets: dict[str, dict[str, bytes]], notes: str = "Nouveautés"):
        assets = []
        for nom, contenu in paquets.items():
            chemin = racine / "files" / nom
            with zipfile.ZipFile(chemin, "w") as z:
                for membre, donnees in contenu.items():
                    z.writestr(f"{nom[:-4]}/{membre}", donnees)
            empreinte = hashlib.sha256(chemin.read_bytes()).hexdigest()
            (racine / "files" / f"{nom}.sha256").write_text(f"{empreinte}  {nom}\n", encoding="ascii")
            for n in (nom, f"{nom}.sha256"):
                assets.append({"name": n, "browser_download_url": f"{base}/files/{n}",
                               "size": (racine / "files" / n).stat().st_size})
        (racine / "api").mkdir(exist_ok=True)
        (racine / "api" / "latest").write_text(json.dumps({
            "tag_name": f"v{version}", "body": notes, "html_url": f"{base}/page", "assets": assets}),
            encoding="utf-8")
        return f"{base}/api/latest"

    yield publier
    httpd.shutdown()


@pytest.fixture
def installation(tmp_path, monkeypatch):
    """Application 1.2 installée + dossier de données à ne jamais toucher."""
    donnees = tmp_path / "LocalAppData" / "MuseeZoune"
    donnees.mkdir(parents=True)
    (donnees / "musee.db").write_bytes(b"base precieuse")
    monkeypatch.setattr(config, "DOSSIER_DONNEES", donnees)
    app = tmp_path / "Documents" / "Musee Zoune"
    (app / "_internal").mkdir(parents=True)
    (app / maj.NOM_EXE).write_bytes(b"exe 1.2")
    (app / "_internal" / "lib.dll").write_bytes(b"lib 1.2")
    monkeypatch.setattr(maj, "journal_script", lambda: tmp_path / "maj.log")
    return app, donnees


def appliquer(attente, app, pid=0, timeout=90):
    commande = maj.commande_script(attente, app, pid, relancer=False)
    return subprocess.run(commande, timeout=timeout, capture_output=True, text=True)


def contenu(app):
    return {p.relative_to(app).as_posix(): p.read_bytes() for p in sorted(app.rglob("*")) if p.is_file()}


def test_mise_a_jour_legere(serveur, installation):
    app, donnees = installation
    url = serveur("1.3", {"MuseeZoune-1.3-maj-depuis-1.0.zip": {
        "Musee Zoune/Musee Zoune.exe": b"exe 1.3", "source/README.md": b"code", "MISE_A_JOUR.txt": b"x"}})

    release = maj.verifier(url)
    assert maj.plus_recente(release.version, "1.2")
    choix = maj.choisir_paquet(release, "1.2")
    assert choix.mode == "fichiers"
    attente = maj.preparer(release, choix, app)
    assert (app / maj.NOM_EXE).read_bytes() == b"exe 1.2"  # rien ne change avant la fermeture

    r = appliquer(attente, app)
    assert r.returncode == 0, r.stdout + r.stderr
    assert contenu(app) == {"Musee Zoune.exe": b"exe 1.3", "_internal/lib.dll": b"lib 1.2"}
    assert not attente.exists()
    assert (donnees / "musee.db").read_bytes() == b"base precieuse"


def test_installation_complete_remplace_le_dossier(serveur, installation):
    app, donnees = installation
    (app / "_internal" / "ancienne.dll").write_bytes(b"a supprimer")
    url = serveur("2.0", {"MuseeZoune-2.0-windows.zip": {
        "Musee Zoune/Musee Zoune.exe": b"exe 2.0", "Musee Zoune/_internal/lib.dll": b"lib 2.0",
        "LISEZMOI.txt": b"lisez-moi"}}, notes=f"Grosse version\n{maj.MARQUEUR_COMPLETE}")

    release = maj.verifier(url)
    choix = maj.choisir_paquet(release, "1.2")
    assert choix.mode == "dossier"
    attente = maj.preparer(release, choix, app)
    r = appliquer(attente, app)
    assert r.returncode == 0, r.stdout + r.stderr
    assert contenu(app) == {"Musee Zoune.exe": b"exe 2.0", "_internal/lib.dll": b"lib 2.0"}
    assert not attente.exists() and not (app.parent / "Musee Zoune.ancien").exists()
    assert (donnees / "musee.db").read_bytes() == b"base precieuse"


def test_retour_arriere_si_un_fichier_est_bloque(serveur, installation):
    app, _ = installation
    url = serveur("1.3", {"MuseeZoune-1.3-maj-depuis-1.2.zip": {
        "Musee Zoune/Musee Zoune.exe": b"exe 1.3", "Musee Zoune/_internal/lib.dll": b"lib 1.3"}})
    release = maj.verifier(url)
    attente = maj.preparer(release, maj.choisir_paquet(release, "1.2"), app)
    avant = contenu(app)
    with open(app / "_internal" / "lib.dll", "rb"):  # ouvert : ni renommage ni remplacement possible
        r = appliquer(attente, app)
    assert r.returncode == 1
    assert contenu(app) == avant  # l'exe éventuellement remplacé est remis, aucun .old ne reste
    assert not attente.exists()


def test_retour_arriere_installation_complete(serveur, installation):
    app, _ = installation
    url = serveur("2.0", {"MuseeZoune-2.0-windows.zip": {
        "Musee Zoune/Musee Zoune.exe": b"exe 2.0", "Musee Zoune/_internal/lib.dll": b"lib 2.0"}},
        notes=maj.MARQUEUR_COMPLETE)
    release = maj.verifier(url)
    attente = maj.preparer(release, maj.choisir_paquet(release, "1.2"), app)
    avant = contenu(app)
    # le nouveau dossier ne peut pas être déplacé : l'ancien doit revenir à sa place
    with open(attente / "fichiers" / "_internal" / "lib.dll", "rb"):
        r = appliquer(attente, app)
    assert r.returncode == 1
    assert contenu(app) == avant and not (app.parent / "Musee Zoune.ancien").exists()


def test_le_script_attend_la_fermeture_de_l_application(serveur, installation):
    app, _ = installation
    url = serveur("1.3", {"MuseeZoune-1.3-maj-depuis-1.2.zip": {"Musee Zoune/Musee Zoune.exe": b"exe 1.3"}})
    release = maj.verifier(url)
    attente = maj.preparer(release, maj.choisir_paquet(release, "1.2"), app)
    appli = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(4)"])
    debut = time.monotonic()
    script = subprocess.Popen(maj.commande_script(attente, app, appli.pid, relancer=False))
    time.sleep(1.5)
    assert script.poll() is None and (app / maj.NOM_EXE).read_bytes() == b"exe 1.2"
    assert script.wait(60) == 0
    assert time.monotonic() - debut >= 3.5
    assert (app / maj.NOM_EXE).read_bytes() == b"exe 1.3"
    appli.wait()


def test_lancement_reel_du_script_comme_l_application(serveur, installation):
    """Même lancement que l'exe (sans fenêtre, processus indépendant)."""
    app, _ = installation
    url = serveur("1.3", {"MuseeZoune-1.3-maj-depuis-1.2.zip": {"Musee Zoune/Musee Zoune.exe": b"exe 1.3"}})
    release = maj.verifier(url)
    attente = maj.preparer(release, maj.choisir_paquet(release, "1.2"), app)
    fermee = subprocess.Popen([sys.executable, "-c", "pass"])
    fermee.wait()  # l'application « vient de se fermer »
    assert maj.lancer_application(attente, app, fermee.pid, relancer=False).wait(60) == 0
    assert (app / maj.NOM_EXE).read_bytes() == b"exe 1.3" and not attente.exists()


def test_serveur_injoignable_leve_une_erreur():
    with pytest.raises(Exception):
        maj.verifier("http://127.0.0.1:9/api/latest")
