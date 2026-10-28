"""Vue générale d'un mois : expositions en bandes, événements en pastilles."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .. import calendrier as cal
from ..textes import jour_court, t
from . import style
from .donnees import Donnees, Element

H_ENTETE = 24       # noms des jours
H_NUMERO = 20       # numéro du jour dans chaque case
H_BANDE = 17
H_PASTILLE = 17
MAX_PASTILLES = 7
H_MIN_SEMAINE = 96


def bandes_empilees(elements: list[Element], lundi: date) -> list[cal.Bande]:
    """Pistes de la semaine : vie perso en haut, expositions en dessous."""
    perso = [e for e in elements if e.nature == "perso"]
    autres = sorted((e for e in elements if e.nature != "perso"), key=lambda e: e.debut)
    haut = cal.bandes_semaine([(e.cle, e.premier_jour, e.dernier_jour) for e in perso], lundi)
    bas = cal.bandes_semaine([(e.cle, e.premier_jour, e.dernier_jour) for e in autres], lundi)
    decalage = max((b.piste + 1 for b in haut), default=0)
    for b in bas:
        b.piste += decalage
    return haut + bas


class VueMois(QWidget):
    element_clique = Signal(object)        # Element
    jour_double_clique = Signal(object)    # date
    jour_choisi = Signal(object)           # date (clic sur « +n autres » ou le numéro)

    def __init__(self, donnees: Donnees, parent=None):
        super().__init__(parent)
        self.donnees = donnees
        self.annee, self.mois = date.today().year, date.today().month
        self.selection: str | None = None
        self._zones: list[tuple[QRectF, object]] = []
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.recalculer()

    # ------------------------------------------------------------------

    def afficher_mois(self, annee: int, mois: int) -> None:
        self.annee, self.mois = annee, mois
        self.recalculer()

    def recalculer(self) -> None:
        self.lundis = cal.semaines_du_mois(self.annee, self.mois)
        debut, fin = self.lundis[0], self.lundis[-1] + timedelta(days=6)
        self.elements = self.donnees.elements(debut, fin)
        self.semaines = []
        for lundi in self.lundis:
            bandes_el = [e for e in self.elements if e.journee and e.dernier_jour >= lundi
                         and e.premier_jour <= lundi + timedelta(days=6)]
            par_cle = {e.cle: e for e in bandes_el}
            bandes = bandes_empilees(bandes_el, lundi)
            n_pistes = max((b.piste + 1 for b in bandes), default=0)
            jours = []
            for i in range(7):
                jour = lundi + timedelta(days=i)
                ponctuels = sorted(
                    (e for e in self.elements if not e.journee
                     and e.premier_jour <= jour <= e.dernier_jour),
                    key=lambda e: (e.debut.time(), e.titre))
                jours.append(ponctuels)
            max_p = min(max((len(j) for j in jours), default=0), MAX_PASTILLES + 1)
            hauteur = max(H_MIN_SEMAINE, H_NUMERO + n_pistes * H_BANDE + 4 + max_p * H_PASTILLE + 6)
            self.semaines.append({"lundi": lundi, "bandes": bandes, "par_cle": par_cle,
                                  "n_pistes": n_pistes, "jours": jours, "hauteur": hauteur})
        self.setMinimumHeight(H_ENTETE + sum(s["hauteur"] for s in self.semaines) + 2)
        self.update()

    # ------------------------------------------------------------------

    def _largeur_jour(self) -> float:
        return (self.width() - 1) / 7

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("white"))
        self._zones = []
        lj = self._largeur_jour()

        p.setFont(style.police(9, True))
        p.setPen(style.COULEUR_TEXTE_PALE)
        for i in range(7):
            p.drawText(QRectF(i * lj, 0, lj, H_ENTETE), Qt.AlignCenter, jour_court(i))

        y = H_ENTETE
        aujourdhui = date.today()
        for sem in self.semaines:
            h = sem["hauteur"]
            for i in range(7):
                jour = sem["lundi"] + timedelta(days=i)
                case = QRectF(i * lj, y, lj, h)
                if jour == aujourdhui:
                    p.fillRect(case, style.COULEUR_AUJOURDHUI)
                elif jour.month != self.mois:
                    p.fillRect(case, style.COULEUR_HORS_MOIS)
                elif i >= 5:
                    p.fillRect(case, style.COULEUR_WEEKEND)
                p.setPen(QPen(style.COULEUR_GRILLE))
                p.drawRect(case)
                p.setFont(style.police(9, jour == aujourdhui))
                p.setPen(style.COULEUR_TEXTE if jour.month == self.mois else style.COULEUR_TEXTE_PALE)
                numero = QRectF(case.left() + 4, y + 2, lj - 8, H_NUMERO - 2)
                p.drawText(numero, Qt.AlignLeft | Qt.AlignVCenter,
                           f"{jour.day}" if jour.day != 1 else f"1 {t('mois').split()[jour.month - 1]}")
                self._zones.append((QRectF(case.left(), y, lj, H_NUMERO), ("jour", jour)))

            # bandes (vie perso puis expositions)
            for b in sem["bandes"]:
                el: Element = sem["par_cle"][b.cle]
                x0 = (b.debut - sem["lundi"]).days * lj + 2
                x1 = ((b.fin - sem["lundi"]).days + 1) * lj - 2
                r = QRectF(x0, y + H_NUMERO + b.piste * H_BANDE, x1 - x0, H_BANDE - 2)
                style.dessiner_fond(p, r, el, 2)
                titre = ("◂ " if b.coupe_gauche else "") + el.titre
                style.dessiner_texte(p, r, titre, el, 8, gras=el.nature == "expo")
                self._contour_selection(p, r, el)
                self._zones.append((r, el))

            # pastilles des événements ponctuels
            y0 = y + H_NUMERO + sem["n_pistes"] * H_BANDE + 4
            for i, ponctuels in enumerate(sem["jours"]):
                jour = sem["lundi"] + timedelta(days=i)
                visibles = ponctuels if len(ponctuels) <= MAX_PASTILLES + 1 else ponctuels[:MAX_PASTILLES]
                for k, el in enumerate(visibles):
                    r = QRectF(i * lj + 2, y0 + k * H_PASTILLE, lj - 4, H_PASTILLE - 2)
                    style.dessiner_fond(p, r, el, 3)
                    heure = el.debut.strftime("%H:%M") if el.debut.date() == jour else "…"
                    style.dessiner_texte(p, r, f"{heure} {el.titre}", el, 8)
                    self._contour_selection(p, r, el)
                    self._zones.append((r, el))
                reste = len(ponctuels) - len(visibles)
                if reste:
                    r = QRectF(i * lj + 4, y0 + len(visibles) * H_PASTILLE, lj - 8, H_PASTILLE - 2)
                    p.setFont(style.police(8, True))
                    p.setPen(style.COULEUR_TEXTE_PALE)
                    p.drawText(r, Qt.AlignLeft | Qt.AlignVCenter, t("plus_n", n=reste))
                    self._zones.append((r, ("jour", jour)))
            y += h
        p.end()

    def _contour_selection(self, p: QPainter, r: QRectF, el: Element) -> None:
        if el.cle == self.selection:
            p.save()
            p.setPen(QPen(QColor("#1A1A1A"), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), 3, 3)
            p.restore()

    # ------------------------------------------------------------------

    def _trouver(self, pos: QPointF):
        for rect, cible in reversed(self._zones):
            if rect.contains(pos):
                return cible
        return None

    def _jour_sous(self, pos: QPointF) -> date | None:
        y = H_ENTETE
        for sem in self.semaines:
            if y <= pos.y() < y + sem["hauteur"]:
                i = min(6, max(0, int(pos.x() // self._largeur_jour())))
                return sem["lundi"] + timedelta(days=i)
            y += sem["hauteur"]
        return None

    def mousePressEvent(self, ev):
        cible = self._trouver(ev.position())
        if isinstance(cible, Element):
            self.selection = cible.cle
            self.update()
            self.element_clique.emit(cible)
        elif isinstance(cible, tuple) and cible[0] == "jour":
            self.jour_choisi.emit(cible[1])

    def mouseDoubleClickEvent(self, ev):
        cible = self._trouver(ev.position())
        if isinstance(cible, Element) and cible.nature == "perso":
            self.element_clique.emit(cible)
            return
        jour = self._jour_sous(ev.position())
        if jour and not isinstance(cible, Element):
            self.jour_double_clique.emit(jour)

    def mouseMoveEvent(self, ev):
        cible = self._trouver(ev.position())
        if isinstance(cible, Element):
            self.setCursor(Qt.PointingHandCursor)
            QToolTip.showText(ev.globalPosition().toPoint(), cible.titre, self)
        elif isinstance(cible, tuple):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()
            QToolTip.hideText()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.update()
