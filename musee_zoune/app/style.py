"""Dessin commun aux deux vues."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from .. import calendrier as cal
from .donnees import Element

COULEUR_GRILLE = QColor("#D0D0D0")
COULEUR_HORS_MOIS = QColor("#F4F4F4")
COULEUR_WEEKEND = QColor("#FAF8F2")
COULEUR_AUJOURDHUI = QColor("#FFF4D6")
COULEUR_TEXTE = QColor("#222222")
COULEUR_TEXTE_PALE = QColor("#888888")
COULEUR_ANNULE = QColor("#B00020")


def police(taille: float = 9, gras: bool = False) -> QFont:
    f = QFont()
    f.setPointSizeF(taille)
    f.setBold(gras)
    return f


def dessiner_fond(p: QPainter, rect: QRectF, el: Element, rayon: float = 3) -> None:
    """Fond d'un élément : plein pour le musée, hachuré + pointillé pour la vie perso."""
    p.save()
    if el.nature == "perso":
        p.setPen(QPen(QColor(cal.COULEUR_PERSO), 1.2, Qt.DashLine))
        p.setBrush(QColor(cal.COULEUR_PERSO_FOND))
        p.drawRoundedRect(rect, rayon, rayon)
        hachures = QBrush(QColor(cal.COULEUR_PERSO).lighter(150), Qt.BDiagPattern)
        p.setPen(Qt.NoPen)
        p.setBrush(hachures)
        p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), rayon, rayon)
    else:
        couleur = QColor(el.couleur)
        p.setPen(QPen(couleur.darker(130), 1))
        p.setBrush(couleur)
        p.drawRoundedRect(rect, rayon, rayon)
        if el.nature == "event" and el.expo_liee:
            # liseré gauche plus foncé : rappelle l'exposition
            p.setPen(Qt.NoPen)
            p.setBrush(couleur.darker(135))
            p.drawRect(QRectF(rect.left(), rect.top(), 3, rect.height()))
    p.restore()


def dessiner_texte(p: QPainter, rect: QRectF, texte: str, el: Element, taille: float = 8.5,
                   gras: bool = False, multiligne: bool = False) -> None:
    p.save()
    f = police(taille, gras)
    f.setStrikeOut(el.annule)
    p.setFont(f)
    p.setPen(COULEUR_ANNULE if el.annule else (QColor("#4A2C82") if el.nature == "perso" else COULEUR_TEXTE))
    zone = rect.adjusted(5 if el.expo_liee else 4, 0, -3, 0)
    if multiligne:
        p.drawText(zone, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, texte)
    else:
        texte = p.fontMetrics().elidedText(texte, Qt.ElideRight, int(zone.width()))
        p.drawText(zone, Qt.AlignLeft | Qt.AlignVCenter, texte)
    p.restore()
