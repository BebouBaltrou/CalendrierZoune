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


COULEUR_SANS_POST = QColor("#E8590C")
COULEUR_POST_PREVU = QColor("#1971C2")
COULEUR_POST_PUBLIE = QColor("#2B8A3E")
TAILLE_INDICATEUR = 9


def a_un_indicateur(el: Element) -> bool:
    """Indicateur de post sur les événements du musée encore à venir."""
    from datetime import date
    return el.nature in ("event", "expo") and el.fin.date() >= date.today() and not el.annule


def dessiner_indicateur(p: QPainter, rect: QRectF, el: Element, en_haut: bool = False) -> float:
    """Pastille à droite de `rect` : orange plein = pas de post, cercle bleu = prévu,
    coche verte = publié. Renvoie la largeur occupée (0 si rien)."""
    if not a_un_indicateur(el):
        return 0
    d = TAILLE_INDICATEUR
    x = rect.right() - d - 3
    y = rect.top() + 3 if en_haut else rect.center().y() - d / 2
    zone = QRectF(x, y, d, d)
    p.save()
    if el.etat_post is None:
        p.setPen(QPen(QColor("white"), 1.2))
        p.setBrush(COULEUR_SANS_POST)
        p.drawEllipse(zone)
    elif el.etat_post == "prevu":
        p.setPen(QPen(COULEUR_POST_PREVU, 1.8))
        p.setBrush(QColor("white"))
        p.drawEllipse(zone)
    else:
        p.setPen(Qt.NoPen)
        p.setBrush(COULEUR_POST_PUBLIE)
        p.drawEllipse(zone)
        p.setPen(QPen(QColor("white"), 1.6))
        p.drawLine(zone.left() + 2.2, zone.center().y(), zone.center().x() - 0.5, zone.bottom() - 2.2)
        p.drawLine(zone.center().x() - 0.5, zone.bottom() - 2.2, zone.right() - 2, zone.top() + 2.2)
    p.restore()
    return d + 4
