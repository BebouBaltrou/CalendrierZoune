"""Colonne de gauche : mini-calendrier et filtres (cases à cocher colorées)."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from .. import calendrier as cal
from .. import db
from .. import theme as th_mod
from ..textes import date_lisible, jour_court, nom_mois, t
from ..theme import SOMBRE
from . import style
from .donnees import Donnees

COULEUR_LIEUX = "#8AB4F8"
COULEUR_POSTS = "#FF8A50"


class MiniCalendrier(QWidget):
    """Petit calendrier du mois : clic sur un jour = aller à cette date."""

    date_choisie = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        aujourdhui = date.today()
        self.annee, self.mois = aujourdhui.year, aujourdhui.month
        self.selection = aujourdhui
        self.setFixedHeight(232)
        self.setMouseTracking(True)
        self._survol: date | None = None

    def montrer(self, jour: date) -> None:
        self.selection = jour
        self.annee, self.mois = jour.year, jour.month
        self.update()

    def _jours(self) -> list[date]:
        debut = cal.lundi_de(date(self.annee, self.mois, 1))
        return [debut + timedelta(days=i) for i in range(42)]

    def _case(self, i: int) -> QRectF:
        c = (self.width() - 16) / 7
        return QRectF(8 + (i % 7) * c, 58 + (i // 7) * 28, c, 28)

    def paintEvent(self, _):
        th = SOMBRE
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(th.fond_panneau))
        p.setFont(style.police(10, poids=500))
        p.setPen(QColor(th.texte))
        p.drawText(QRectF(14, 4, self.width() - 80, 28), Qt.AlignLeft | Qt.AlignVCenter,
                   f"{nom_mois(self.mois).capitalize()} {self.annee}")
        p.setFont(style.police(12))
        p.setPen(QColor(th.texte_secondaire))
        self._fleches = (QRectF(self.width() - 68, 4, 28, 28), QRectF(self.width() - 36, 4, 28, 28))
        p.drawText(self._fleches[0], Qt.AlignCenter, "‹")
        p.drawText(self._fleches[1], Qt.AlignCenter, "›")
        p.setFont(style.police(7.5, poids=600))
        for i in range(7):
            r = self._case(i)
            p.drawText(QRectF(r.left(), 34, r.width(), 22), Qt.AlignCenter, jour_court(i)[0].upper())
        aujourdhui = date.today()
        p.setFont(style.police(8))
        for i, jour in enumerate(self._jours()):
            r = self._case(i)
            rond = QRectF(r.center().x() - 12, r.center().y() - 12, 24, 24)
            if jour == aujourdhui:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(th_mod.COULEUR_ACCENT))
                p.drawEllipse(rond)
                p.setPen(QColor(th.aujourdhui_texte))
            else:
                if jour == self.selection or jour == self._survol:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor("#394457" if jour == self.selection else th.fond_survol))
                    p.drawEllipse(rond)
                p.setPen(QColor(th.texte if jour.month == self.mois else th.texte_attenue))
            p.drawText(rond, Qt.AlignCenter, str(jour.day))
        p.end()

    def _jour_sous(self, pos: QPointF) -> date | None:
        for i, jour in enumerate(self._jours()):
            if self._case(i).contains(pos):
                return jour
        return None

    def mousePressEvent(self, ev):
        pos = ev.position()
        for sens, zone in zip((-1, 1), getattr(self, "_fleches", ())):
            if zone.contains(pos):
                m = self.mois - 1 + sens
                self.annee, self.mois = self.annee + m // 12, m % 12 + 1
                self.update()
                return
        jour = self._jour_sous(pos)
        if jour:
            self.selection = jour
            self.update()
            self.date_choisie.emit(jour)

    def mouseMoveEvent(self, ev):
        jour = self._jour_sous(ev.position())
        if jour != self._survol:
            self._survol = jour
            self.setCursor(Qt.PointingHandCursor if jour else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, _):
        self._survol = None
        self.update()


class CaseCouleur(QWidget):
    """Case à cocher dans la couleur de l'élément, façon Google Agenda."""

    basculee = Signal(bool)

    def __init__(self, texte: str, couleur: str, coche: bool = True, perso: bool = False, parent=None):
        super().__init__(parent)
        self.texte, self.couleur, self.coche, self.perso = texte, couleur, coche, perso
        self.setFixedHeight(30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(texte)
        self._survol = False

    def sizeHint(self) -> QSize:
        return QSize(200, 30)

    def paintEvent(self, _):
        th = SOMBRE
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._survol:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(th.fond_survol))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(4, 0, -4, 0), 6, 6)
        case = QRectF(14, 7, 16, 16)
        couleur = QColor(self.couleur)
        if self.coche:
            p.setPen(Qt.NoPen)
            p.setBrush(couleur)
            p.drawRoundedRect(case, 3, 3)
            p.setPen(QPen(QColor(th_mod.texte_sur(self.couleur)), 2))
            p.drawLine(QPointF(case.left() + 3.5, case.center().y()),
                       QPointF(case.left() + 6.5, case.bottom() - 4))
            p.drawLine(QPointF(case.left() + 6.5, case.bottom() - 4),
                       QPointF(case.right() - 3, case.top() + 4))
        else:
            p.setPen(QPen(couleur, 2, Qt.DashLine if self.perso else Qt.SolidLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(case.adjusted(1, 1, -1, -1), 3, 3)
        p.setFont(style.police(9.5))
        p.setPen(QColor(th.texte))
        zone = QRectF(40, 0, self.width() - 48, self.height())
        p.drawText(zone, Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(self.texte, Qt.ElideRight, int(zone.width())))
        p.end()

    def mousePressEvent(self, _):
        self.coche = not self.coche
        self.update()
        self.basculee.emit(self.coche)

    def enterEvent(self, _):
        self._survol = True
        self.update()

    def leaveEvent(self, _):
        self._survol = False
        self.update()


class Section(QWidget):
    """Titre cliquable (replier / déplier) + contenu."""

    def __init__(self, titre: str, parent=None):
        super().__init__(parent)
        self.entete = QToolButton()
        self.entete.setCheckable(False)
        self.entete.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.entete.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.entete.setStyleSheet("QToolButton { text-align: left; font-weight: 600; padding: 8px 12px;"
                                  " border-radius: 0; }")
        self.entete.clicked.connect(self.basculer)
        self.contenu = QWidget()
        self.lignes = QVBoxLayout(self.contenu)
        self.lignes.setContentsMargins(0, 0, 0, 6)
        self.lignes.setSpacing(0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.entete)
        layout.addWidget(self.contenu)
        self.ouverte = True
        self.set_titre(titre)

    def set_titre(self, titre: str) -> None:
        self.titre = titre
        self.entete.setText(titre)
        self.entete.setIcon(style.icone("deplier" if self.ouverte else "replier", "#9AA0A6", 14))

    def basculer(self) -> None:
        self.ouverte = not self.ouverte
        self.contenu.setVisible(self.ouverte)
        self.set_titre(self.titre)

    def vider(self) -> None:
        while self.lignes.count():
            item = self.lignes.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def ajouter(self, widget: QWidget) -> None:
        self.lignes.addWidget(widget)


class BarreLaterale(QWidget):
    date_choisie = Signal(object)
    filtres_changes = Signal()

    def __init__(self, donnees: Donnees, parent=None):
        super().__init__(parent)
        self.donnees = donnees
        self.setFixedWidth(272)
        self.mini = MiniCalendrier()
        self.mini.date_choisie.connect(self.date_choisie)

        self.s_expos = Section(t("legende_titre"))
        self.s_types = Section("")
        self.s_lieux = Section("")
        self.s_perso = Section("")
        self.s_posts = Section("")
        contenu = QWidget()
        self._contenu = contenu
        pile = QVBoxLayout(contenu)
        pile.setContentsMargins(0, 0, 0, 0)
        pile.setSpacing(2)
        for s in (self.s_expos, self.s_types, self.s_lieux, self.s_perso, self.s_posts):
            pile.addWidget(s)
        pile.addStretch()
        defilement = QScrollArea()
        defilement.setWidgetResizable(True)
        defilement.setFrameShape(QScrollArea.NoFrame)
        defilement.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        defilement.setWidget(contenu)

        self.statut = QLabel()
        self.statut.setWordWrap(True)
        self.statut.setStyleSheet("color: #9AA0A6; font-size: 8.5pt; padding: 8px 14px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.mini)
        layout.addWidget(defilement, 1)
        layout.addWidget(self.statut)
        self._periode = (date.today(), date.today())

    def set_statut(self, texte: str, alerte: bool = False) -> None:
        self.statut.setText(texte)
        self.statut.setStyleSheet(
            f"color: {'#FDD663' if alerte else '#9AA0A6'}; font-size: 8.5pt; padding: 8px 14px;")

    def remplir(self, debut: date, fin: date) -> None:
        """Reconstruit les sections (les expositions dépendent de la période affichée)."""
        self._periode = (debut, fin)
        d = self.donnees
        self.s_expos.set_titre(t("legende_titre"))
        self.s_types.set_titre(t("filtre_types"))
        self.s_lieux.set_titre(t("filtre_lieux"))
        self.s_perso.set_titre(t("perso_titre"))
        self.s_posts.set_titre(t("post_titre"))
        for s in (self.s_expos, self.s_types, self.s_lieux, self.s_perso, self.s_posts):
            s.vider()

        for expo in d.expos_visibles(debut, fin):
            premier, dernier = cal.jours_de(expo)
            case = CaseCouleur(expo["title"], d.couleur_expo(expo["uid"]), expo["uid"] not in d.expos_masquees)
            case.setToolTip(f"{expo['title']}\n{date_lisible(premier, True)} → {date_lisible(dernier, True)}"
                            f"\n{', '.join(x for x in (expo.get('venue'), expo.get('city')) if x)}")
            case.basculee.connect(lambda c, u=expo["uid"]: self._basculer(d.expos_masquees, u, c))
            self.s_expos.ajouter(case)

        for type_ in d.types():
            case = CaseCouleur(t("type_" + type_), th_mod.COULEURS_TYPES.get(type_, "#5F6368")
                               if type_ != "exposition" else "#9AA0A6", type_ not in d.types_masques)
            case.basculee.connect(lambda c, x=type_: self._basculer(d.types_masques, x, c))
            self.s_types.ajouter(case)

        for ville in d.villes():
            case = CaseCouleur(ville, COULEUR_LIEUX, ville not in d.villes_masquees)
            case.basculee.connect(lambda c, x=ville: self._basculer(d.villes_masquees, x, c))
            self.s_lieux.ajouter(case)

        for type_ in db.TYPES_PERSO:
            case = CaseCouleur(t("perso_type_" + type_), th_mod.COULEUR_PERSO,
                               type_ not in d.perso_masques, perso=True)
            case.basculee.connect(lambda c, x=type_: self._basculer(d.perso_masques, x, c))
            self.s_perso.ajouter(case)

        sans_post = CaseCouleur(t("filtre_sans_post_seul"), COULEUR_POSTS, d.sans_post_seulement)
        sans_post.setToolTip(t("filtre_sans_post_aide"))
        sans_post.basculee.connect(self._sans_post)
        self.s_posts.ajouter(sans_post)
        libres = CaseCouleur(t("filtre_posts_libres"), th_mod.COULEUR_ACCENT, d.avec_posts_libres)
        libres.basculee.connect(self._posts_libres)
        self.s_posts.ajouter(libres)
        for etat, cle in ((None, "legende_sans_post"), ("prevu", "legende_post_prevu"),
                          ("publie", "legende_post_publie")):
            self.s_posts.ajouter(_LegendeIndicateur(etat, t(cle)))
        # recalcule tout de suite la hauteur des sections reconstruites
        for section in (self.s_expos, self.s_types, self.s_lieux, self.s_perso, self.s_posts):
            section.lignes.activate()
            section.contenu.adjustSize()
            section.adjustSize()
        self._contenu.layout().activate()
        self._contenu.adjustSize()

    def _basculer(self, ensemble: set, cle: str, coche: bool) -> None:
        (ensemble.discard if coche else ensemble.add)(cle)
        self.filtres_changes.emit()

    def _sans_post(self, coche: bool) -> None:
        self.donnees.sans_post_seulement = coche
        self.filtres_changes.emit()

    def _posts_libres(self, coche: bool) -> None:
        self.donnees.avec_posts_libres = coche
        self.filtres_changes.emit()


class _LegendeIndicateur(QWidget):
    """Ligne de légende des pastilles de post (non cliquable)."""

    def __init__(self, etat: str | None, texte: str, parent=None):
        super().__init__(parent)
        self.etat, self.texte = etat, texte
        self.setFixedHeight(22)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        style.indicateur_icone(self.etat).paint(p, 15, 3, 16, 16)
        p.setFont(style.police(8.5))
        p.setPen(QColor(SOMBRE.texte_secondaire))
        p.drawText(QRectF(40, 0, self.width() - 44, self.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   self.texte)
        p.end()
