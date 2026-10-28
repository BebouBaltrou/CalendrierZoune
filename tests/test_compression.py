"""Compression de photos et de PDF."""

import os
from pathlib import Path

import pytest
from PIL import Image

from musee_zoune import compression as cp


def photo(chemin: Path, taille=(4000, 3000), mode="RGB") -> Path:
    """Photo « bruitée » (difficile à compresser) pour des tailles réalistes."""
    bruit = Image.frombytes("L", taille, os.urandom(taille[0] * taille[1])).convert(mode)
    img = Image.merge(mode, [bruit.getchannel(0)] * len(mode)) if mode != "RGB" else Image.merge(
        "RGB", [bruit.getchannel(0), Image.linear_gradient("L").resize(taille), bruit.getchannel(0)])
    if chemin.suffix.lower() == ".png":
        img.save(chemin)
    else:
        img.save(chemin, quality=95)
    return chemin


def test_mail_moins_de_2_mo_et_1600_px(tmp_path):
    src = photo(tmp_path / "vernissage.jpg")
    avant = src.read_bytes()
    r = cp.compresser(src, cp.PREREGLAGES["mail"])
    assert r.ok and r.sortie.name == "vernissage_mail.jpg"
    assert r.apres < 2_000_000 and r.apres < r.avant
    with Image.open(r.sortie) as img:
        assert max(img.size) <= 1600
    assert src.read_bytes() == avant  # original intact


def test_web_1200_px(tmp_path):
    r = cp.compresser(photo(tmp_path / "a.jpg", (3000, 2000)), cp.PREREGLAGES["web"])
    with Image.open(r.sortie) as img:
        assert img.size == (1200, 800)


def test_jamais_d_ecrasement(tmp_path):
    src = photo(tmp_path / "b.jpg", (800, 600))
    r1 = cp.compresser(src, cp.PREREGLAGES["web"])
    r2 = cp.compresser(src, cp.PREREGLAGES["web"])
    assert r1.sortie.name == "b_web.jpg" and r2.sortie.name == "b_web_2.jpg"


def test_png_transparent_reste_png(tmp_path):
    src = tmp_path / "logo.png"
    img = Image.new("RGBA", (2000, 1000), (255, 0, 0, 0))
    img.paste((20, 40, 200, 255), (100, 100, 1900, 900))
    img.save(src)
    r = cp.compresser(src, cp.PREREGLAGES["mail"])
    assert r.sortie.suffix == ".png"
    with Image.open(r.sortie) as sortie:
        assert sortie.mode == "RGBA" and max(sortie.size) <= 1600


def test_heic(tmp_path):
    if not cp.HEIC_OK:
        pytest.skip("pillow-heif absent")
    src = tmp_path / "iphone.heic"
    Image.new("RGB", (3000, 2000), (30, 120, 200)).save(src)
    r = cp.compresser(src, cp.PREREGLAGES["mail"])
    assert r.ok and r.sortie.name == "iphone_mail.jpg"


def test_reglage_perso():
    reglage = cp.reglage_perso(800, 200)
    assert reglage.qualite == 95 and reglage.max_px == 800 and reglage.nom == "perso"


def test_format_non_pris_en_charge(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("bonjour")
    r = cp.compresser(src, cp.PREREGLAGES["mail"])
    assert not r.ok and r.sortie is None


def test_pdf_avec_grosse_image(tmp_path):
    import pymupdf
    image = photo(tmp_path / "scan.jpg", (3500, 2500))
    src = tmp_path / "dossier_presse.pdf"
    doc = pymupdf.open()
    for _ in range(2):
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, filename=str(image))
        page.insert_text((50, 50), "Dossier de presse BLMK")
    doc.save(src)
    doc.close()

    r = cp.compresser(src, cp.PREREGLAGES["mail"])
    assert r.ok and r.sortie.name == "dossier_presse_mail.pdf"
    assert r.apres < r.avant / 3
    resultat = pymupdf.open(r.sortie)
    assert resultat.page_count == 2 and "Dossier de presse" in resultat[0].get_text()
    resultat.close()


def test_pdf_corrompu_ne_plante_pas(tmp_path):
    src = tmp_path / "casse.pdf"
    src.write_bytes(b"%PDF-1.4 pas vraiment un pdf")
    r = cp.compresser(src, cp.PREREGLAGES["web"])
    assert not r.ok and r.message
