"""Mises à jour de l'application depuis les Releases GitHub.

Convention des fichiers joints à une release (produits par outils/construire_paquet.py) :

    MuseeZoune-<v>-windows.zip                 installation complète
    MuseeZoune-<v>-maj-depuis-<base>.zip       mise à jour légère (le nouvel exe), valable
                                               pour toute version installée >= <base>
    <nom du zip>.sha256                        empreinte SHA-256 de chaque zip (obligatoire)

Si les notes de la release contiennent la ligne MARQUEUR_COMPLETE, ou s'il n'y a pas de
mise à jour légère valable pour la version installée, l'installation complète est utilisée.

L'exécutable en cours ne peut pas être remplacé pendant que l'application tourne :
PyInstaller relit le code Python dans l'exe à chaque import. Le nouveau contenu est donc
préparé (téléchargé, vérifié, dézippé) à côté du dossier de l'application, dans
« <dossier>.maj », puis un petit script PowerShell attend la fermeture de l'application,
fait l'échange (anciens fichiers renommés en .old, retour arrière en cas d'échec) et
relance l'application si demandé. Le dossier des données (%LOCALAPPDATA%\\MuseeZoune)
n'est jamais touché.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Callable

import requests

from . import config

log = logging.getLogger("musee_zoune.maj")

MARQUEUR_COMPLETE = "<!-- musee-zoune: installation-complete -->"
RE_MAJ = re.compile(r"^MuseeZoune-(?P<v>[0-9][\w.]*)-maj-depuis-(?P<base>[0-9][\w.]*)\.zip$")
RE_COMPLET = re.compile(r"^MuseeZoune-(?P<v>[0-9][\w.]*)-windows\.zip$")
DOSSIER_DANS_ZIP = "Musee Zoune"   # <racine du zip>/Musee Zoune/… = contenu de l'application
NOM_EXE = "Musee Zoune.exe"
TIMEOUT_VERIF = 10
TIMEOUT_TELECHARGEMENT = 60


class ErreurMaj(Exception):
    """Mise à jour impossible (téléchargement, empreinte, archive, emplacement…)."""


# ---------------------------------------------------------------------- versions

def version_tuple(texte: str) -> tuple[tuple[int, ...], int]:
    """« v1.2 » → ((1, 2), 1). « 1.2.0 » == « 1.2 ». Une préversion (« 1.2-beta ») passe avant."""
    m = re.match(r"^\s*[vV]?(\d+(?:\.\d+)*)(.*)$", texte or "")
    if not m:
        raise ValueError(f"version illisible : {texte!r}")
    nombres = [int(x) for x in m.group(1).split(".")]
    while len(nombres) > 1 and nombres[-1] == 0:
        nombres.pop()
    return tuple(nombres), 0 if m.group(2).strip() else 1


def plus_recente(a: str, b: str) -> bool:
    """La version `a` est-elle strictement plus récente que `b` ?"""
    return version_tuple(a) > version_tuple(b)


def meme_version(a: str, b: str) -> bool:
    return version_tuple(a) == version_tuple(b)


# ---------------------------------------------------------------------- release

@dataclass
class Fichier:
    nom: str
    url: str
    taille: int = 0


@dataclass
class Release:
    version: str
    notes: str
    page: str
    fichiers: dict[str, Fichier]

    @property
    def complete_imposee(self) -> bool:
        return MARQUEUR_COMPLETE in self.notes

    def notes_affichables(self) -> str:
        return "\n".join(l for l in self.notes.splitlines() if MARQUEUR_COMPLETE not in l).strip()


@dataclass
class Choix:
    mode: str          # "fichiers" (mise à jour légère) ou "dossier" (installation complète)
    archive: Fichier
    empreinte: Fichier


def lire_release(donnees: dict) -> Release:
    fichiers = {a["name"]: Fichier(a["name"], a["browser_download_url"], int(a.get("size") or 0))
                for a in donnees.get("assets") or []}
    return Release(version=str(donnees.get("tag_name") or "").lstrip("vV"),
                   notes=donnees.get("body") or "", page=donnees.get("html_url") or "",
                   fichiers=fichiers)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = config.USER_AGENT
    return s


def verifier(url: str | None = None, session: requests.Session | None = None) -> Release:
    """Dernière release publiée. Lève une exception si pas d'internet ou réponse invalide."""
    session = session or _session()
    r = session.get(url or config.URL_MAJ, timeout=TIMEOUT_VERIF,
                    headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    release = lire_release(r.json())
    version_tuple(release.version)  # tag illisible : erreur
    return release


def choisir_paquet(release: Release, installee: str) -> Choix | None:
    """Paquet à installer pour passer de `installee` à `release.version`.

    None si la release n'est pas plus récente, ou si aucun paquet utilisable (avec son
    empreinte .sha256) n'est joint.
    """
    if not plus_recente(release.version, installee):
        return None
    if not release.complete_imposee:
        candidats = []
        for nom, f in release.fichiers.items():
            m = RE_MAJ.match(nom)
            if (m and meme_version(m["v"], release.version) and not plus_recente(m["base"], installee)
                    and f"{nom}.sha256" in release.fichiers):
                candidats.append((version_tuple(m["base"]), f))
        if candidats:
            f = max(candidats, key=lambda c: c[0])[1]
            return Choix("fichiers", f, release.fichiers[f"{f.nom}.sha256"])
    for nom, f in release.fichiers.items():
        m = RE_COMPLET.match(nom)
        if m and meme_version(m["v"], release.version) and f"{nom}.sha256" in release.fichiers:
            return Choix("dossier", f, release.fichiers[f"{nom}.sha256"])
    return None


# ---------------------------------------------------------------------- empreintes

def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def lire_empreinte(texte: str) -> str:
    """Format « <64 hexa>  <nom du fichier> » (sha256sum) ou juste l'empreinte."""
    morceaux = texte.strip().split()
    if not morceaux or not re.fullmatch(r"[0-9a-fA-F]{64}", morceaux[0]):
        raise ErreurMaj("fichier d'empreinte illisible")
    return morceaux[0].lower()


def verifier_empreinte(chemin: Path, attendue: str) -> None:
    obtenue = sha256_fichier(chemin)
    if obtenue != attendue.lower():
        raise ErreurMaj(f"empreinte SHA-256 incorrecte pour {chemin.name} "
                        f"(attendue {attendue[:12]}…, obtenue {obtenue[:12]}…)")


# ---------------------------------------------------------------------- emplacements

def dossier_application() -> Path:
    """Dossier contenant « Musee Zoune.exe » (version installée uniquement)."""
    return Path(sys.executable).resolve().parent


def dossier_attente(application: Path) -> Path:
    """Contenu préparé, à côté du dossier de l'application (même disque : renommage possible)."""
    return application.parent / f"{application.name}.maj"


def journal_script() -> Path:
    return Path(tempfile.gettempdir()) / "MuseeZoune-maj.log"


def _dedans(a: Path, b: Path) -> bool:
    a, b = a.resolve(), b.resolve()
    return a == b or b in a.parents


def verifier_emplacement(application: Path) -> None:
    """Refuse de travailler si le dossier de l'application et celui des données se recouvrent."""
    donnees = config.DOSSIER_DONNEES
    if _dedans(application, donnees) or _dedans(donnees, application) \
            or _dedans(dossier_attente(application), donnees):
        raise ErreurMaj(f"le dossier de l'application ({application}) recouvre celui des données")
    if not (application / NOM_EXE).exists():
        raise ErreurMaj(f"{NOM_EXE} introuvable dans {application}")


# ---------------------------------------------------------------------- préparation

def telecharger(fichier: Fichier, cible: Path, session: requests.Session | None = None,
                arreter: Callable[[], bool] = lambda: False) -> Path:
    session = session or _session()
    partiel = cible.with_name(cible.name + ".partiel")
    with session.get(fichier.url, stream=True, timeout=TIMEOUT_TELECHARGEMENT) as r:
        r.raise_for_status()
        with open(partiel, "wb") as f:
            for bloc in r.iter_content(1 << 16):
                if arreter():
                    raise ErreurMaj("téléchargement interrompu")
                f.write(bloc)
    partiel.replace(cible)
    return cible


def extraire_application(archive: Path, destination: Path) -> list[str]:
    """Copie dans `destination` le contenu de « <racine>/Musee Zoune/ » du zip."""
    fichiers = []
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ErreurMaj("archive endommagée")
        for info in z.infolist():
            chemin = PurePosixPath(info.filename)
            parties = chemin.parts
            if info.is_dir() or len(parties) < 3 or parties[1] != DOSSIER_DANS_ZIP:
                continue
            relatif = PurePosixPath(*parties[2:])
            if chemin.is_absolute() or ".." in relatif.parts or ":" in info.filename:
                raise ErreurMaj(f"chemin interdit dans l'archive : {info.filename}")
            cible = destination.joinpath(*relatif.parts)
            cible.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(cible, "wb") as dst:
                shutil.copyfileobj(src, dst)
            fichiers.append(relatif.as_posix())
    return fichiers


def preparer(release: Release, choix: Choix, application: Path,
             session: requests.Session | None = None,
             arreter: Callable[[], bool] = lambda: False) -> Path:
    """Télécharge, vérifie et dézippe la nouvelle version dans le dossier d'attente.

    En cas d'échec, le dossier d'attente est supprimé et l'application n'est pas modifiée.
    """
    verifier_emplacement(application)
    session = session or _session()
    attente = dossier_attente(application)
    shutil.rmtree(attente, ignore_errors=True)
    try:
        telechargement = attente / "telechargement"
        telechargement.mkdir(parents=True)
        r = session.get(choix.empreinte.url, timeout=TIMEOUT_VERIF)
        r.raise_for_status()
        attendue = lire_empreinte(r.text)
        archive = telecharger(choix.archive, telechargement / choix.archive.nom, session, arreter)
        verifier_empreinte(archive, attendue)
        fichiers = extraire_application(archive, attente / "fichiers")
        if NOM_EXE not in fichiers:
            raise ErreurMaj(f"{NOM_EXE} absent de {choix.archive.nom}")
        if choix.mode == "dossier" and not any(f.startswith("_internal/") for f in fichiers):
            raise ErreurMaj(f"{choix.archive.nom} n'est pas une installation complète")
        shutil.rmtree(telechargement)
        (attente / "maj.json").write_text(json.dumps({
            "version": release.version, "mode": choix.mode, "paquet": choix.archive.nom,
            "prepare_le": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
        log.info("mise à jour %s préparée (%s, %d fichier(s))", release.version, choix.mode, len(fichiers))
        return attente
    except BaseException:
        shutil.rmtree(attente, ignore_errors=True)
        raise


# ---------------------------------------------------------------------- application

SCRIPT = r"""
param(
    [Parameter(Mandatory = $true)][string]$Attente,
    [Parameter(Mandatory = $true)][string]$Cible,
    [Parameter(Mandatory = $true)][ValidateSet('fichiers', 'dossier')][string]$Mode,
    [int]$AttendrePid = 0,
    [string]$Exe = 'Musee Zoune.exe',
    [string]$Journal = '',
    [switch]$Relancer
)
# Applique une mise a jour de Musee Zoune apres la fermeture de l'application.
# Ne touche qu'au dossier de l'application ($Cible) et au dossier d'attente ($Attente).
$ErrorActionPreference = 'Stop'
function Ecrire([string]$Message) {
    if ($Journal) {
        try { Add-Content -LiteralPath $Journal -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message) -Encoding UTF8 } catch {}
    }
}
function Reessayer([scriptblock]$Action) {
    for ($i = 1; $i -le 40; $i++) {
        try { & $Action; return } catch { if ($i -eq 40) { throw }; Start-Sleep -Milliseconds 250 }
    }
}

$cheminExe = Join-Path $Cible $Exe
# attendre la fermeture de l'application (ce processus et toute autre instance)
while ($true) {
    $actifs = @()
    if ($AttendrePid -gt 0) { $actifs += @(Get-Process -Id $AttendrePid -ErrorAction SilentlyContinue) }
    $actifs += @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $cheminExe })
    if ($actifs.Count -eq 0) { break }
    Start-Sleep -Seconds 1
}

# une seule application de la mise a jour, meme si plusieurs scripts attendent
try { Rename-Item -LiteralPath (Join-Path $Attente 'maj.json') -NewName 'maj.en-cours.json' }
catch { Ecrire "rien a appliquer dans $Attente"; exit 0 }

$source = Join-Path $Attente 'fichiers'
$ok = $false
Ecrire "debut ($Mode) : $source -> $Cible"
if ($Mode -eq 'fichiers') {
    $faits = New-Object System.Collections.ArrayList
    try {
        $base = (Resolve-Path -LiteralPath $source).Path.TrimEnd('\') + '\'
        foreach ($f in @(Get-ChildItem -LiteralPath $source -Recurse -File)) {
            $dest = Join-Path $Cible $f.FullName.Substring($base.Length)
            $existait = Test-Path -LiteralPath $dest
            $dossier = Split-Path -Parent $dest
            if (-not (Test-Path -LiteralPath $dossier)) { New-Item -ItemType Directory -Path $dossier | Out-Null }
            if ($existait) {
                if (Test-Path -LiteralPath "$dest.old") { Remove-Item -LiteralPath "$dest.old" -Force }
                Reessayer { Move-Item -LiteralPath $dest -Destination "$dest.old" }
            }
            [void]$faits.Add(@($dest, $existait))
            Reessayer { Copy-Item -LiteralPath $f.FullName -Destination $dest }
        }
        $ok = $true
    } catch {
        Ecrire "echec : $_ ; retour arriere"
        for ($i = $faits.Count - 1; $i -ge 0; $i--) {
            $dest = $faits[$i][0]
            try {
                if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Force }
                if ($faits[$i][1]) { Move-Item -LiteralPath "$dest.old" -Destination $dest }
            } catch { Ecrire "retour arriere impossible pour $dest : $_" }
        }
    }
    if ($ok) {
        foreach ($e in $faits) {
            if ($e[1]) { Remove-Item -LiteralPath "$($e[0]).old" -Force -ErrorAction SilentlyContinue }
        }
    }
} else {
    $ancien = "$Cible.ancien"
    $deplace = $false
    try {
        if (Test-Path -LiteralPath $ancien) { Remove-Item -LiteralPath $ancien -Recurse -Force }
        Reessayer { Move-Item -LiteralPath $Cible -Destination $ancien }
        $deplace = $true
        Reessayer { Move-Item -LiteralPath $source -Destination $Cible }
        $ok = $true
    } catch {
        Ecrire "echec : $_ ; retour arriere"
        if ($deplace) {
            try {
                if (Test-Path -LiteralPath $Cible) { Remove-Item -LiteralPath $Cible -Recurse -Force }
                Move-Item -LiteralPath $ancien -Destination $Cible
            } catch { Ecrire "retour arriere impossible : $_" }
        }
    }
    if ($ok) { Remove-Item -LiteralPath $ancien -Recurse -Force -ErrorAction SilentlyContinue }
}

Remove-Item -LiteralPath $Attente -Recurse -Force -ErrorAction SilentlyContinue
if ($ok) { Ecrire 'mise a jour appliquee' } else { Ecrire 'mise a jour abandonnee, ancienne version conservee' }
if ($Relancer -and (Test-Path -LiteralPath $cheminExe)) { Start-Process -FilePath $cheminExe -WorkingDirectory $Cible }
if ($ok) { exit 0 } else { exit 1 }
"""


def commande_script(attente: Path, application: Path, pid: int, relancer: bool) -> list[str]:
    infos = json.loads((attente / "maj.json").read_text(encoding="utf-8"))
    script = Path(tempfile.gettempdir()) / "MuseeZoune-appliquer-maj.ps1"
    script.write_text(SCRIPT.lstrip(), encoding="utf-8-sig")  # BOM : Windows PowerShell 5.1
    commande = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden", "-File", str(script),
                "-Attente", str(attente), "-Cible", str(application), "-Mode", infos["mode"],
                "-AttendrePid", str(pid), "-Exe", NOM_EXE, "-Journal", str(journal_script())]
    return commande + (["-Relancer"] if relancer else [])


def lancer_application(attente: Path, application: Path, pid: int, relancer: bool) -> subprocess.Popen:
    """Lance le script qui appliquera la mise à jour dès que l'application sera fermée."""
    drapeaux = 0
    if os.name == "nt":
        # pas DETACHED_PROCESS : sans console, powershell.exe quitte sans rien exécuter
        drapeaux = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    log.info("script de mise à jour lancé (relancer=%s)", relancer)
    return subprocess.Popen(commande_script(attente, application, pid, relancer),
                            creationflags=drapeaux, close_fds=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def appliquer_en_attente() -> bool:
    """Au lancement : une mise à jour préparée n'a pas été appliquée (PC éteint avant la
    fermeture, par ex.) → lancer le script avec relance et quitter tout de suite (True)."""
    if not config.est_installee():
        return False
    application = dossier_application()
    attente = dossier_attente(application)
    if not (attente / "maj.json").exists():
        return False
    try:
        verifier_emplacement(application)
        lancer_application(attente, application, os.getpid(), relancer=True)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("mise à jour en attente non appliquée : %s", exc)
        shutil.rmtree(attente, ignore_errors=True)
        return False


def nettoyer(application: Path | None = None) -> None:
    """Supprime les restes d'une mise à jour déjà appliquée (*.old, dossier .ancien)."""
    if application is None:
        if not config.est_installee():
            return
        application = dossier_application()
    for ancien in application.rglob("*.old"):
        try:
            ancien.unlink()
        except OSError:
            pass
    shutil.rmtree(application.parent / f"{application.name}.ancien", ignore_errors=True)
