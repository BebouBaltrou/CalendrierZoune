"""Export PDF du calendrier (A4 paysage) : vue mois ou vue semaine, avec légende."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QMarginsF, QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from .. import calendrier as cal
from ..theme import CLAIR
from ..textes import date_lisible, nom_mois, t
from . import style
from .donnees import Donnees
from .vue_mois import VueMois
from .vue_semaine import VueSemaine

RESOLUTION = 150  # points par pouce dans le PDF
H_TITRE = 70


def titre_periode(vue: str, jour: date) -> str:
    if vue == "semaine":
        lundi = cal.lundi_de(jour)
        return t("semaine_num", num=lundi.isocalendar()[1], debut=date_lisible(lundi),
                 fin=date_lisible(lundi + timedelta(days=6), True))
    return f"{nom_mois(jour.month).capitalize()} {jour.year}"


def nom_fichier(vue: str, jour: date) -> str:
    if vue == "semaine":
        return f"BLMK_{t('vue_semaine').lower()}_{cal.lundi_de(jour).isocalendar()[1]}_{jour.year}.pdf"
    return f"BLMK_{nom_mois(jour.month)}_{jour.year}.pdf"


def _legende(p: QPainter, donnees: Donnees, zone: QRectF, debut: date, fin: date, avec_perso: bool) -> None:
    """Légende des couleurs en colonnes, en bas de page."""
    entrees = [(donnees.couleur_expo(e["uid"]), e["title"], False)
               for e in donnees.expos_visibles(debut, fin) if e["uid"] not in donnees.expos_masquees]
    entrees.append((cal.COULEURS_TYPES["atelier"], t("legende_autres"), False))
    if avec_perso:
        entrees.append((cal.COULEUR_PERSO, t("legende_vie_perso"), True))
    colonnes = 3
    largeur = zone.width() / colonnes
    p.setFont(style.police(7.5))
    for i, (couleur, texte, perso) in enumerate(entrees):
        x = zone.left() + (i % colonnes) * largeur
        y = zone.top() + (i // colonnes) * 20
        carre = QRectF(x, y + 3, 14, 14)
        if perso:
            p.setPen(QPen(QColor(cal.COULEUR_PERSO), 1.2, Qt.DashLine))
            p.setBrush(QColor(CLAIR.perso_fond))
        else:
            p.setPen(QPen(QColor(couleur).darker(130)))
            p.setBrush(QColor(couleur))
        p.drawRoundedRect(carre, 3, 3)
        p.setPen(QColor("#333333"))
        texte = p.fontMetrics().elidedText(texte, Qt.ElideRight, int(largeur - 30))
        p.drawText(QRectF(x + 20, y, largeur - 24, 20), Qt.AlignVCenter | Qt.AlignLeft, texte)


def hauteur_legende(donnees: Donnees, debut: date, fin: date, avec_perso: bool) -> float:
    n = len([e for e in donnees.expos_visibles(debut, fin) if e["uid"] not in donnees.expos_masquees])
    n += 2 if avec_perso else 1
    return ((n + 2) // 3) * 20 + 10


def exporter(conn, chemin: Path | str, vue: str, jour: date, compact: bool = False,
             avec_perso: bool = True, ville: str | None = None,
             expos_masquees: set[str] | None = None, modele: Donnees | None = None) -> Path:
    """Écrit le PDF (thème clair) et renvoie son chemin. Nécessite une QApplication.

    `modele` : les filtres de l'écran (expositions, types, lieux… décochés) sont repris.
    """
    chemin = Path(chemin)
    donnees = Donnees(conn)
    if modele is not None:
        for attribut in ("villes_masquees", "types_masques", "expos_masquees", "perso_masques"):
            setattr(donnees, attribut, set(getattr(modele, attribut)))
        donnees.sans_post_seulement = modele.sans_post_seulement
        donnees.avec_posts = modele.avec_posts
        donnees.recherche = modele.recherche
    donnees.avec_perso = avec_perso
    donnees.ville = ville
    if expos_masquees is not None:
        donnees.expos_masquees = set(expos_masquees)

    ecrivain = QPdfWriter(str(chemin))
    ecrivain.setResolution(RESOLUTION)
    ecrivain.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape,
                                       QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter))
    ecrivain.setTitle(f"{t('app_titre')} — {titre_periode(vue, jour)}")
    ecrivain.setCreator("Musée Zoune")

    p = QPainter(ecrivain)
    p.setRenderHint(QPainter.Antialiasing)
    largeur, hauteur = ecrivain.width(), ecrivain.height()

    # en-tête : titre de l'application + période
    p.setPen(QColor("#202124"))
    p.setFont(style.police(16, True))
    p.drawText(QRectF(0, 0, largeur, 40), Qt.AlignLeft | Qt.AlignVCenter, titre_periode(vue, jour))
    p.setFont(style.police(8))
    p.setPen(QColor("#5f6368"))
    sous_titre = t("app_titre") + (f" · {ville}" if ville else "")
    p.drawText(QRectF(0, 0, largeur, 40), Qt.AlignRight | Qt.AlignVCenter, sous_titre)
    p.drawText(QRectF(0, 40, largeur, 22), Qt.AlignRight | Qt.AlignVCenter,
               datetime.now().strftime("%d/%m/%Y %H:%M"))

    # vue dessinée par le même code qu'à l'écran
    if vue == "semaine":
        widget = VueSemaine(donnees, theme=CLAIR)
        widget.afficher_semaine(jour)
        debut, fin = widget.lundi, widget.lundi + timedelta(days=6)
    else:
        widget = VueMois(donnees, theme=CLAIR)
        widget.compact = compact
        widget.afficher_mois(jour.year, jour.month)
        debut, fin = widget.lundis[0], widget.lundis[-1] + timedelta(days=6)
    h_leg = hauteur_legende(donnees, debut, fin, avec_perso)
    zone = QRectF(0, H_TITRE, largeur, hauteur - H_TITRE - h_leg - 10)

    if vue != "semaine" and compact:
        widget.hauteur_imposee = zone.height()
        widget.resize(int(zone.width()), int(zone.height()))
        widget.recalculer()
    widget.resize(int(zone.width()), max(widget.minimumHeight(), 10))
    widget.selection = None
    echelle = min(1.0, zone.height() / widget.height())
    p.save()
    p.translate(zone.left(), zone.top())
    p.scale(echelle, echelle)
    # si on réduit, on élargit le widget pour qu'il garde toute la largeur de la page
    if echelle < 1.0:
        widget.resize(int(zone.width() / echelle), widget.height())
    widget.render(p, QPoint(0, 0))
    p.restore()

    _legende(p, donnees, QRectF(0, hauteur - h_leg, largeur, h_leg), debut, fin, avec_perso)
    p.end()
    widget.deleteLater()
    return chemin
