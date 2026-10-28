"""Construit la version à envoyer : dist/MuseeZoune-<version>-windows.zip

    .venv\\Scripts\\python outils\\construire_paquet.py

Contenu du zip :
    Musee Zoune/        l'application (double-cliquer sur « Musee Zoune.exe »)
    LISEZMOI.txt        mode d'emploi court, français et allemand
    source/             code source du projet (obligation de la licence AGPL de PyMuPDF)
    licences/           licences des bibliothèques incluses
"""

import importlib.metadata as md
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from musee_zoune.config import VERSION  # noqa: E402

DIST = RACINE / "dist"
NOM = f"MuseeZoune-{VERSION}-windows"
DEPENDANCES = ["PySide6", "PySide6_Essentials", "shiboken6", "Pillow", "pillow_heif", "PyMuPDF",
               "requests", "urllib3", "certifi", "charset_normalizer", "idna", "beautifulsoup4",
               "soupsieve"]

LISEZMOI = """MUSÉE ZOUNE {version} — programmation du BLMK
==============================================

FRANÇAIS
--------
1. Dézippez ce fichier (clic droit > « Extraire tout… »), par exemple dans « Documents ».
2. Ouvrez le dossier « Musee Zoune » et double-cliquez sur « Musee Zoune.exe ».
   Astuce : clic droit sur le fichier > « Envoyer vers » > « Bureau (créer un raccourci) ».
3. Au premier lancement, Windows peut afficher « Windows a protégé votre ordinateur »
   (l'application n'est pas signée) : cliquez sur « Informations complémentaires »,
   puis sur « Exécuter quand même ».

Au premier lancement, l'application récupère toute seule la programmation sur
www.blmk.de (connexion internet nécessaire), puis une fois par jour au démarrage.
Le bouton « Actualiser » (flèche circulaire en haut) relance la récupération.

Vos données (calendrier, Vie de Zoune, posts, réglages) sont enregistrées dans :
    %LOCALAPPDATA%\\MuseeZoune
(copiez « %LOCALAPPDATA%\\MuseeZoune » dans la barre d'adresse de l'explorateur).
Pour sauvegarder ou changer d'ordinateur, copiez ce dossier. Supprimer le dossier de
l'application ne supprime pas vos données.

Pour désinstaller : supprimez le dossier « Musee Zoune » (et, si vous le souhaitez,
le dossier %LOCALAPPDATA%\\MuseeZoune).

DEUTSCH
-------
1. Diese Datei entpacken (Rechtsklick > „Alle extrahieren…“), z. B. in „Dokumente“.
2. Den Ordner „Musee Zoune“ öffnen und „Musee Zoune.exe“ doppelklicken.
   Tipp: Rechtsklick auf die Datei > „Senden an“ > „Desktop (Verknüpfung erstellen)“.
3. Beim ersten Start zeigt Windows eventuell „Der Computer wurde durch Windows geschützt“
   (die Anwendung ist nicht signiert): auf „Weitere Informationen“ und dann auf
   „Trotzdem ausführen“ klicken.

Beim ersten Start lädt die Anwendung das Programm von www.blmk.de automatisch herunter
(Internetverbindung erforderlich), danach einmal täglich beim Start. Die Schaltfläche
„Aktualisieren“ (runder Pfeil oben) startet den Abruf erneut. Die Sprache lässt sich
oben rechts umstellen (FR / DE).

Ihre Daten (Kalender, Zounes Leben, Posts, Einstellungen) liegen in:
    %LOCALAPPDATA%\\MuseeZoune
Zum Sichern oder für einen neuen Computer diesen Ordner kopieren. Das Löschen des
Anwendungsordners löscht Ihre Daten nicht.

Deinstallieren: den Ordner „Musee Zoune“ löschen (und bei Bedarf %LOCALAPPDATA%\\MuseeZoune).

LICENCES / LIZENZEN
-------------------
Ce logiciel inclut des bibliothèques libres (voir le dossier « licences »), dont PyMuPDF
(AGPL-3.0) : le code source complet de l'application est fourni dans le dossier « source ».
Diese Software enthält freie Bibliotheken (siehe Ordner „licences“), u. a. PyMuPDF
(AGPL-3.0): der vollständige Quellcode liegt im Ordner „source“.
"""


def construire_exe() -> Path:
    commande = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", "Musee Zoune", "--icon", str(RACINE / "assets" / "icone.ico"),
        "--add-data", f"{RACINE / 'assets' / 'icone.png'};assets",
        "--collect-all", "pillow_heif",
        # PyMuPDF embarque un module de mise en page IA (onnxruntime, numpy) inutile ici
        "--exclude-module", "onnxruntime", "--exclude-module", "numpy",
        "--exclude-module", "pymupdf.layout", "--exclude-module", "pytest",
        "--exclude-module", "tkinter", "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.QtQml", "--exclude-module", "PySide6.QtNetwork",
        "--distpath", str(DIST), "--workpath", str(RACINE / "build"), "--specpath", str(RACINE / "build"),
        str(RACINE / "Musee Zoune.pyw"),
    ]
    subprocess.run(commande, check=True, cwd=RACINE)
    return DIST / "Musee Zoune"


def copier_licences(dossier: Path) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    resume = ["Bibliothèques incluses dans Musée Zoune et leurs licences", ""]
    for nom in DEPENDANCES:
        try:
            dist = md.distribution(nom)
        except md.PackageNotFoundError:
            continue
        licence = dist.metadata.get("License-Expression") or dist.metadata.get("License") or ""
        if len(licence) > 80:
            licence = licence.splitlines()[0][:80]
        classif = [c.split("::")[-1].strip() for c in dist.metadata.get_all("Classifier") or []
                   if c.startswith("License ::")]
        resume.append(f"- {dist.metadata['Name']} {dist.version} : {licence or ', '.join(classif) or 'voir fichiers'}")
        cible = dossier / f"{dist.metadata['Name']}-{dist.version}"
        for fichier in dist.files or []:
            if any(m in fichier.name.upper() for m in ("LICENSE", "LICENCE", "COPYING", "NOTICE")):
                source = Path(dist.locate_file(fichier))
                if source.is_file():
                    cible.mkdir(exist_ok=True)
                    shutil.copy2(source, cible / source.name)
    resume += ["", "Python " + sys.version.split()[0] + " : licence PSF (https://docs.python.org/3/license.html)",
               "Qt 6 : LGPL-3.0 (via PySide6)",
               "libheif (LGPL-3.0), libde265 (LGPL-3.0), x265 (GPL-2.0) : via pillow-heif",
               "MuPDF : AGPL-3.0 (via PyMuPDF) — code source de l'application dans « source/ »."]
    (dossier / "LICENCES.txt").write_text("\n".join(resume) + "\n", encoding="utf-8")


def copier_source(dossier: Path) -> None:
    """Code source suivi par git (sans .venv, data, dist, build)."""
    archive = RACINE / "build" / "source.zip"
    archive.parent.mkdir(exist_ok=True)
    subprocess.run(["git", "archive", "--format=zip", "-o", str(archive), "HEAD"], check=True, cwd=RACINE)
    with zipfile.ZipFile(archive) as z:
        z.extractall(dossier)


MISE_A_JOUR = """MUSÉE ZOUNE — MISE À JOUR {ancienne} → {version}
==============================================

FRANÇAIS
--------
Cette mise à jour s'installe sur la version {ancienne} déjà installée.
1. Fermez Musée Zoune.
2. Dézippez ce fichier.
3. Copiez le fichier « Musee Zoune.exe » (dossier « Musee Zoune » de ce zip) dans votre
   dossier « Musee Zoune » existant, à la place de l'ancien : choisissez
   « Remplacer le fichier dans la destination ».
4. Relancez Musée Zoune. Menu « ⋯ » > « À propos » affiche la version {version}.
Vos données (%LOCALAPPDATA%\\MuseeZoune) ne sont pas modifiées.
Si Windows affiche « Windows a protégé votre ordinateur » : « Informations complémentaires »,
puis « Exécuter quand même ».

DEUTSCH
-------
Dieses Update wird auf die bereits installierte Version {ancienne} angewendet.
1. Musée Zoune schließen.
2. Diese Datei entpacken.
3. Die Datei „Musee Zoune.exe“ (Ordner „Musee Zoune“ in diesem ZIP) in Ihren vorhandenen
   Ordner „Musee Zoune“ kopieren und „Datei im Ziel ersetzen“ wählen.
4. Musée Zoune neu starten. Menü „⋯“ > „Über Musée Zoune“ zeigt die Version {version}.
Ihre Daten (%LOCALAPPDATA%\\MuseeZoune) bleiben unverändert.
Falls Windows „Der Computer wurde durch Windows geschützt“ anzeigt: „Weitere Informationen“,
dann „Trotzdem ausführen“.

Le code source complet est dans le dossier « source » (licence AGPL de PyMuPDF).
Der vollständige Quellcode liegt im Ordner „source“ (AGPL-Lizenz von PyMuPDF).
"""

VERSIONS = RACINE / "versions"  # empreintes des versions publiées (suivi par git)


def _empreinte(donnees: bytes) -> str:
    import hashlib
    return hashlib.sha256(donnees).hexdigest()


def manifeste_dossier(dossier: Path) -> dict[str, str]:
    """{chemin relatif : sha256} de tous les fichiers de l'application."""
    return {f.relative_to(dossier).as_posix(): _empreinte(f.read_bytes())
            for f in sorted(dossier.rglob("*")) if f.is_file()}


def manifeste_zip(chemin_zip: Path) -> dict[str, str]:
    """Empreinte d'une version à partir de son zip complet déjà distribué."""
    resultat = {}
    with zipfile.ZipFile(chemin_zip) as z:
        for nom in z.namelist():
            morceaux = nom.split("/", 2)
            if len(morceaux) == 3 and morceaux[1] == "Musee Zoune" and not nom.endswith("/"):
                resultat[morceaux[2]] = _empreinte(z.read(nom))
    return resultat


def manifeste_version(version: str) -> dict[str, str] | None:
    fichier = VERSIONS / f"MuseeZoune-{version}.json"
    if fichier.exists():
        return json.loads(fichier.read_text(encoding="utf-8"))
    zip_complet = DIST / f"MuseeZoune-{version}-windows.zip"
    if zip_complet.exists():
        manifeste = manifeste_zip(zip_complet)
        enregistrer_manifeste(version, manifeste)
        return manifeste
    return None


def enregistrer_manifeste(version: str, manifeste: dict[str, str]) -> None:
    VERSIONS.mkdir(exist_ok=True)
    (VERSIONS / f"MuseeZoune-{version}.json").write_text(
        json.dumps(manifeste, indent=1, sort_keys=True), encoding="utf-8")


def comparer(ancien: dict[str, str], nouveau: dict[str, str]) -> tuple[list[str], list[str]]:
    """(fichiers modifiés ou ajoutés, fichiers modifiés hors de l'exe)."""
    changes = [f for f, h in nouveau.items() if ancien.get(f) != h]
    return changes, [f for f in changes if f != "Musee Zoune.exe"]


def paquet_mise_a_jour(application: Path, ancienne: str, forcer: bool = False) -> Path | None:
    ancien = manifeste_version(ancienne)
    if ancien is None:
        print(f"!! Empreinte de la version {ancienne} introuvable : pas de paquet de mise à jour.")
        return None
    changes, autres = comparer(ancien, manifeste_dossier(application))
    if autres and not forcer:
        print(f"!! Les bibliothèques ont changé depuis la {ancienne} ({len(autres)} fichier(s), ex. "
              f"{', '.join(autres[:5])}).\n   Une simple mise à jour ne suffit pas : envoyez le zip complet.")
        return None
    nom = f"MuseeZoune-{VERSION}-maj-depuis-{ancienne}"
    dossier = DIST / nom
    shutil.rmtree(dossier, ignore_errors=True)
    for fichier in changes:
        cible = dossier / "Musee Zoune" / fichier
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(application / fichier, cible)
    (dossier / "MISE_A_JOUR.txt").write_text(
        MISE_A_JOUR.format(version=VERSION, ancienne=ancienne).replace("\n", "\r\n"), encoding="utf-8-sig")
    copier_source(dossier / "source")
    return zipper(dossier, DIST / f"{nom}.zip", nom)


def zipper(dossier: Path, zip_final: Path, racine: str) -> Path:
    zip_final.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_final, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for fichier in sorted(dossier.rglob("*")):
            if fichier.is_file():
                z.write(fichier, Path(racine) / fichier.relative_to(dossier))
    print(f"{zip_final} : {zip_final.stat().st_size / 1048576:.1f} Mo")
    return zip_final


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Construit les zips de Musée Zoune.")
    parser.add_argument("--depuis", help="version précédente pour le paquet de mise à jour (ex. 1.0)")
    parser.add_argument("--forcer", action="store_true",
                        help="créer la mise à jour même si les bibliothèques ont changé")
    parser.add_argument("--maj-seulement", action="store_true",
                        help="ne pas produire le zip complet, seulement la mise à jour")
    args = parser.parse_args()
    if args.depuis:
        manifeste_version(args.depuis)  # à calculer AVANT de reconstruire (zip de l'ancienne version)

    application = construire_exe()
    enregistrer_manifeste(VERSION, manifeste_dossier(application))
    if args.depuis and args.maj_seulement:
        paquet_mise_a_jour(application, args.depuis, args.forcer)
        return
    paquet = DIST / NOM
    shutil.rmtree(paquet, ignore_errors=True)
    paquet.mkdir(parents=True)
    shutil.copytree(application, paquet / "Musee Zoune")
    (paquet / "LISEZMOI.txt").write_text(LISEZMOI.format(version=VERSION).replace("\n", "\r\n"),
                                         encoding="utf-8-sig")
    copier_licences(paquet / "licences")
    copier_source(paquet / "source")
    zipper(paquet, DIST / f"{NOM}.zip", NOM)
    if args.depuis:
        paquet_mise_a_jour(application, args.depuis, args.forcer)


if __name__ == "__main__":
    main()
