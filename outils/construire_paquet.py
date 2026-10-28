"""Construit la version à envoyer : dist/MuseeZoune-<version>-windows.zip

    .venv\\Scripts\\python outils\\construire_paquet.py

Contenu du zip :
    Musee Zoune/        l'application (double-cliquer sur « Musee Zoune.exe »)
    LISEZMOI.txt        mode d'emploi court, français et allemand
    source/             code source du projet (obligation de la licence AGPL de PyMuPDF)
    licences/           licences des bibliothèques incluses
"""

import importlib.metadata as md
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


def main() -> None:
    application = construire_exe()
    paquet = DIST / NOM
    shutil.rmtree(paquet, ignore_errors=True)
    paquet.mkdir(parents=True)
    shutil.copytree(application, paquet / "Musee Zoune")
    (paquet / "LISEZMOI.txt").write_text(LISEZMOI.format(version=VERSION).replace("\n", "\r\n"),
                                         encoding="utf-8-sig")
    copier_licences(paquet / "licences")
    copier_source(paquet / "source")
    zip_final = DIST / f"{NOM}.zip"
    zip_final.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_final, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for fichier in sorted(paquet.rglob("*")):
            if fichier.is_file():
                z.write(fichier, Path(NOM) / fichier.relative_to(paquet))
    print(f"{zip_final} : {zip_final.stat().st_size / 1048576:.0f} Mo")


if __name__ == "__main__":
    main()
