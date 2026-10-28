"""Compression de photos et de PDF, sans dépendance système.

- Photos (JPG, PNG, HEIC, WEBP…) : Pillow + pillow-heif. Redimensionnement, réencodage JPEG
  (PNG conservé s'il y a de la transparence), orientation EXIF appliquée, métadonnées retirées.
- PDF : PyMuPDF (`rewrite_images`) réduit la résolution des images intégrées.

Le fichier compressé est écrit à côté de l'original, avec un suffixe
(`affiche_mail.jpg`) ; l'original n'est jamais modifié ni écrasé.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

try:  # HEIC (photos d'iPhone)
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_OK = True
except ImportError:  # pragma: no cover
    HEIC_OK = False

EXTENSIONS_IMAGES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff", ".bmp"}
EXTENSIONS_PDF = {".pdf"}
POUCES_A4 = 11.69  # grand côté d'une page A4


@dataclass(frozen=True)
class Reglage:
    nom: str             # mail / web / impression / perso (sert de suffixe)
    max_px: int          # plus grand côté des photos
    qualite: int         # qualité JPEG (1-95)
    cible_octets: int | None = None  # taille visée par fichier (mail)

    @property
    def dpi_pdf(self) -> int:
        """Résolution des images dans les PDF, déduite de la taille max en pixels."""
        return max(72, round(self.max_px / POUCES_A4))


PREREGLAGES = {
    "mail": Reglage("mail", 1600, 75, cible_octets=2_000_000),
    "web": Reglage("web", 1200, 80),
    "impression": Reglage("impression", 3500, 92),
}


def reglage_perso(max_px: int, qualite: int) -> Reglage:
    return Reglage("perso", max(100, int(max_px)), min(95, max(10, int(qualite))))


@dataclass
class Resultat:
    source: Path
    sortie: Path | None
    avant: int
    apres: int
    message: str = ""   # vide si tout va bien

    @property
    def ok(self) -> bool:
        return self.sortie is not None and not self.message

    @property
    def gain(self) -> float:
        return 0.0 if not self.avant else 1 - self.apres / self.avant


def chemin_sortie(source: Path, suffixe: str, extension: str) -> Path:
    """`photo.heic` -> `photo_mail.jpg` ; ajoute _2, _3… si le nom est déjà pris."""
    base = source.with_name(f"{source.stem}_{suffixe}{extension}")
    candidat, n = base, 2
    while candidat.exists() or candidat == source:
        candidat = base.with_name(f"{base.stem}_{n}{extension}")
        n += 1
    return candidat


# --------------------------------------------------------------------------
# Photos
# --------------------------------------------------------------------------

def _a_de_la_transparence(img: Image.Image) -> bool:
    if img.mode in ("RGBA", "LA"):
        return img.getchannel("A").getextrema()[0] < 255
    return img.mode == "P" and "transparency" in img.info


def _encoder(img: Image.Image, format_: str, qualite: int) -> bytes:
    tampon = io.BytesIO()
    if format_ == "PNG":
        img.save(tampon, "PNG", optimize=True)
    else:
        img.save(tampon, "JPEG", quality=qualite, optimize=True, progressive=True)
    return tampon.getvalue()


def _reduire(img: Image.Image, max_px: int) -> Image.Image:
    if max(img.size) <= max_px:
        return img
    copie = img.copy()
    copie.thumbnail((max_px, max_px), Image.LANCZOS)
    return copie


def compresser_image(source: Path, reglage: Reglage) -> Resultat:
    source = Path(source)
    avant = source.stat().st_size
    with Image.open(source) as ouverte:
        img = ImageOps.exif_transpose(ouverte)
        img.load()
    transparent = _a_de_la_transparence(img)
    format_ = "PNG" if transparent else "JPEG"
    img = img.convert("RGBA" if transparent else "RGB")

    taille = reglage.max_px
    qualite = reglage.qualite
    donnees = _encoder(_reduire(img, taille), format_, qualite)
    # « Mail » : on descend la qualité puis la taille jusqu'à passer sous la cible
    if reglage.cible_octets:
        while len(donnees) > reglage.cible_octets and (qualite > 45 or taille > 800):
            if format_ == "JPEG" and qualite > 45:
                qualite -= 10
            else:
                taille = int(taille * 0.85)
            donnees = _encoder(_reduire(img, taille), format_, qualite)

    sortie = chemin_sortie(source, reglage.nom, ".png" if format_ == "PNG" else ".jpg")
    sortie.write_bytes(donnees)
    return Resultat(source, sortie, avant, len(donnees))


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------

def _reecrire_pdf(source: Path, dpi: int, qualite: int) -> bytes:
    import pymupdf
    doc = pymupdf.open(source)
    try:
        doc.rewrite_images(dpi_threshold=dpi + 10, dpi_target=dpi, quality=qualite,
                           lossless=True, bitonal=False)
        return doc.tobytes(garbage=4, deflate=True, clean=True)
    finally:
        doc.close()


def compresser_pdf(source: Path, reglage: Reglage) -> Resultat:
    source = Path(source)
    avant = source.stat().st_size
    dpi, qualite = reglage.dpi_pdf, reglage.qualite
    donnees = _reecrire_pdf(source, dpi, qualite)
    if reglage.cible_octets:
        while len(donnees) > reglage.cible_octets and dpi > 72:
            dpi, qualite = max(72, int(dpi * 0.75)), max(40, qualite - 10)
            donnees = _reecrire_pdf(source, dpi, qualite)
    sortie = chemin_sortie(source, reglage.nom, ".pdf")
    sortie.write_bytes(donnees)
    return Resultat(source, sortie, avant, len(donnees))


# --------------------------------------------------------------------------

def est_pris_en_charge(chemin: Path) -> bool:
    ext = Path(chemin).suffix.lower()
    if ext in (".heic", ".heif") and not HEIC_OK:
        return False
    return ext in EXTENSIONS_IMAGES | EXTENSIONS_PDF


def compresser(source: Path, reglage: Reglage) -> Resultat:
    """Compresse un fichier ; ne lève pas d'exception (l'erreur est dans `message`)."""
    source = Path(source)
    try:
        if not source.is_file():
            return Resultat(source, None, 0, 0, "introuvable")
        if source.suffix.lower() in EXTENSIONS_PDF:
            return compresser_pdf(source, reglage)
        if est_pris_en_charge(source):
            return compresser_image(source, reglage)
        return Resultat(source, None, source.stat().st_size, 0, "format non pris en charge")
    except Exception as exc:  # noqa: BLE001 — fichier corrompu, PDF protégé…
        return Resultat(source, None, source.stat().st_size if source.exists() else 0, 0, str(exc))
