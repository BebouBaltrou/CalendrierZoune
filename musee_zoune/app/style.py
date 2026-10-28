"""Dessin commun aux vues (mois, semaine, export) et icônes de l'interface."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap

from .. import theme as th_mod
from ..theme import SOMBRE, Theme, texte_sur
from .donnees import Element

TAILLE_INDICATEUR = 9


def police(taille: float = 9, gras: bool = False, poids: int | None = None) -> QFont:
    f = QFont(th_mod.POLICE)
    f.setPointSizeF(taille)
    if poids is not None:
        f.setWeight(QFont.Weight(poids))
    else:
        f.setBold(gras)
    return f


# --------------------------------------------------------------------------
# Éléments du calendrier
# --------------------------------------------------------------------------

def dessiner_fond(p: QPainter, rect: QRectF, el: Element, rayon: float = 4, th: Theme = SOMBRE) -> None:
    """Bande pleine arrondie ; Vie de Zoune hachurée avec bord pointillé ; post libre en contour."""
    p.save()
    if el.nature == "perso":
        p.setPen(QPen(QColor(th_mod.COULEUR_PERSO), 1.2, Qt.DashLine))
        p.setBrush(QColor(th.perso_fond))
        p.drawRoundedRect(rect, rayon, rayon)
        hachures = QColor(th_mod.COULEUR_PERSO)
        hachures.setAlpha(70)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(hachures, Qt.BDiagPattern))
        p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), rayon, rayon)
    elif el.nature == "post":
        p.setPen(QPen(QColor(th_mod.COULEUR_ACCENT), 1, Qt.DotLine))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), rayon, rayon)
    else:
        couleur = QColor(el.couleur)
        if el.annule:
            couleur.setAlpha(110)
        p.setPen(Qt.NoPen)
        p.setBrush(couleur)
        p.drawRoundedRect(rect, rayon, rayon)
    p.restore()


def couleur_texte(el: Element, th: Theme = SOMBRE) -> QColor:
    if el.nature == "perso":
        return QColor("#E9D5FF" if th.sombre else "#5B2A86")
    if el.nature == "post":
        return QColor(th_mod.COULEUR_ACCENT if th.sombre else "#1A73E8")
    return QColor(texte_sur(el.couleur))


def dessiner_texte(p: QPainter, rect: QRectF, texte: str, el: Element, taille: float = 8.5,
                   gras: bool = False, multiligne: bool = False, th: Theme = SOMBRE) -> None:
    p.save()
    f = police(taille, gras)
    f.setStrikeOut(el.annule)
    p.setFont(f)
    p.setPen(couleur_texte(el, th))
    zone = rect.adjusted(6, 0, -4, 0)
    if multiligne:
        p.drawText(zone, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, texte)
    else:
        texte = p.fontMetrics().elidedText(texte, Qt.ElideRight, int(zone.width()))
        p.drawText(zone, Qt.AlignLeft | Qt.AlignVCenter, texte)
    p.restore()


def contour_selection(p: QPainter, r: QRectF, rayon: float = 4, th: Theme = SOMBRE) -> None:
    p.save()
    p.setPen(QPen(QColor("#FFFFFF" if th.sombre else "#202124"), 2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), rayon + 1, rayon + 1)
    p.restore()


# --------------------------------------------------------------------------
# Indicateur de post
# --------------------------------------------------------------------------

def a_un_indicateur(el: Element) -> bool:
    """Indicateur de post sur les événements du musée encore à venir."""
    return el.nature in ("event", "expo") and el.fin.date() >= date.today() and not el.annule


def dessiner_indicateur(p: QPainter, rect: QRectF, el: Element, en_haut: bool = False) -> float:
    """Pastille à droite de `rect` : orange = pas de post, cercle bleu = prévu, coche verte = publié.
    Renvoie la largeur occupée (0 si rien)."""
    if not a_un_indicateur(el):
        return 0
    d = TAILLE_INDICATEUR
    x = rect.right() - d - 4
    y = rect.top() + 4 if en_haut else rect.center().y() - d / 2
    zone = QRectF(x, y, d, d)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    contour = QPen(QColor(0, 0, 0, 90), 1)
    if el.etat_post is None:
        p.setPen(contour)
        p.setBrush(QColor(th_mod.COULEUR_SANS_POST))
        p.drawEllipse(zone)
    elif el.etat_post == "prevu":
        p.setPen(QPen(QColor(th_mod.COULEUR_POST_PREVU), 2))
        p.setBrush(QColor("#202124"))
        p.drawEllipse(zone)
    else:
        p.setPen(contour)
        p.setBrush(QColor(th_mod.COULEUR_POST_PUBLIE))
        p.drawEllipse(zone)
        p.setPen(QPen(QColor("#202124"), 1.6))
        p.drawLine(zone.left() + 2.2, zone.center().y(), zone.center().x() - 0.5, zone.bottom() - 2.2)
        p.drawLine(zone.center().x() - 0.5, zone.bottom() - 2.2, zone.right() - 2, zone.top() + 2.2)
    p.restore()
    return d + 5


# --------------------------------------------------------------------------
# Icônes (police Segoe Fluent Icons / MDL2 de Windows, sinon texte de repli)
# --------------------------------------------------------------------------

GLYPHES = {
    "menu": ("", "☰"), "recherche": ("", "⌕"), "precedent": ("", "‹"),
    "suivant": ("", "›"), "actualiser": ("", "⟳"), "cloche": ("", "•"),
    "plus_options": ("", "⋯"), "ajouter": ("", "+"), "fermer": ("", "×"),
    "compact": ("", "≡"), "calendrier": ("", "▦"), "langue": ("", "🌐"),
    "outils": ("", "⚙"), "deplier": ("", "▾"), "replier": ("", "▸"),
}
_POLICE_ICONES: str | None = None


def police_icones() -> str | None:
    global _POLICE_ICONES
    if _POLICE_ICONES is None:
        familles = set(QFontDatabase.families())
        _POLICE_ICONES = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in familles), "")
    return _POLICE_ICONES or None


def icone(nom: str, couleur: str = "#E8EAED", taille: int = 20, badge: int = 0) -> QIcon:
    """Icône dessinée à partir d'un glyphe ; `badge` > 0 ajoute une pastille rouge numérotée."""
    pix = QPixmap(taille * 2, taille * 2)
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    glyphe, repli = GLYPHES[nom]
    famille = police_icones()
    f = QFont(famille) if famille else police(10)
    f.setPixelSize(int(taille * (0.8 if famille else 0.9)))
    p.setFont(f)
    p.setPen(QColor(couleur))
    p.drawText(QRectF(0, 0, taille, taille), Qt.AlignCenter, glyphe if famille else repli)
    if badge:
        texte = "9+" if badge > 9 else str(badge)
        r = QRectF(taille * 0.42, 0, taille * 0.58, taille * 0.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#F28B82"))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        fb = police(6.5, True)
        fb.setPixelSize(int(taille * 0.36))
        p.setFont(fb)
        p.setPen(QColor("#202124"))
        p.drawText(r, Qt.AlignCenter, texte)
    p.end()
    return QIcon(pix)


def pastille(couleur: str, taille: int = 14, perso: bool = False) -> QIcon:
    pix = QPixmap(taille, taille)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    if perso:
        p.setPen(QPen(QColor(th_mod.COULEUR_PERSO), 1.2, Qt.DashLine))
        p.setBrush(QColor(SOMBRE.perso_fond))
    else:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(couleur))
    p.drawRoundedRect(QRectF(1, 1, taille - 2, taille - 2), 3, 3)
    p.end()
    return QIcon(pix)


def indicateur_icone(etat: str | None) -> QIcon:
    """Petite icône reprenant l'indicateur de post des vues."""
    from datetime import datetime, timedelta
    pix = QPixmap(16, 16)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    maintenant = datetime.now()
    faux = Element("x", "event", "", "#ffffff", maintenant, maintenant + timedelta(days=1),
                   False, etat_post=etat)
    dessiner_indicateur(p, QRectF(0, 0, 17, 16), faux)
    p.end()
    return QIcon(pix)
