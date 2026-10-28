"""Vue semaine détaillée : bandes en haut, créneaux horaires en dessous."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .. import calendrier as cal
from ..textes import date_lisible, t
from . import style
from .donnees import Donnees, Element
from .vue_mois import bandes_empilees

L_HEURES = 52       # colonne des heures
H_ENTETE = 34
H_BANDE = 19
H_HEURE = 64        # hauteur d'une heure
HEURE_MIN, HEURE_MAX = 8, 21  # plage par défaut, élargie si besoin


class VueSemaine(QWidget):
    element_clique = Signal(object)
    creneau_double_clique = Signal(object)  # datetime

    def __init__(self, donnees: Donnees, parent=None):
        super().__init__(parent)
        self.donnees = donnees
        self.lundi = cal.lundi_de(date.today())
        self.selection: str | None = None
        self._zones: list[tuple[QRectF, Element]] = []
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.recalculer()

    def afficher_semaine(self, jour: date) -> None:
        self.lundi = cal.lundi_de(jour)
        self.recalculer()

    def recalculer(self) -> None:
        dimanche = self.lundi + timedelta(days=6)
        self.elements = self.donnees.elements(self.lundi, dimanche)
        journee = [e for e in self.elements if e.journee]
        self.par_cle = {e.cle: e for e in journee}
        self.bandes = bandes_empilees(journee, self.lundi)
        self.n_pistes = max((b.piste + 1 for b in self.bandes), default=0)

        self.horaires = [e for e in self.elements if not e.journee]
        heures = [e.debut.hour for e in self.horaires] + [
            e.fin.hour + (e.fin.minute > 0) for e in self.horaires if e.fin.date() == e.debut.date()]
        self.h_min = min([HEURE_MIN] + heures)
        self.h_max = max([HEURE_MAX] + heures)
        self.h_max = min(24, self.h_max)

        # colonnes côte à côte, jour par jour
        self.places: dict[str, tuple[int, int]] = {}
        for i in range(7):
            jour = self.lundi + timedelta(days=i)
            du_jour = [(e.cle, *self._bornes_jour(e, jour)) for e in self.horaires
                       if e.premier_jour <= jour <= e.dernier_jour]
            for cle, place in cal.colonnes(du_jour).items():
                self.places[(cle, jour)] = place
        self.setMinimumHeight(int(self._y_grille() + (self.h_max - self.h_min) * H_HEURE + 2))
        self.update()

    def _bornes_jour(self, e: Element, jour: date) -> tuple[datetime, datetime]:
        debut = max(e.debut, datetime.combine(jour, time(self.h_min if hasattr(self, "h_min") else 0)))
        fin = min(e.fin, datetime.combine(jour, time(23, 59)))
        return debut, fin

    def _y_grille(self) -> float:
        return H_ENTETE + self.n_pistes * H_BANDE + (8 if self.n_pistes else 4)

    def _largeur_jour(self) -> float:
        return (self.width() - L_HEURES - 1) / 7

    def _y_heure(self, moment: datetime) -> float:
        heures = moment.hour + moment.minute / 60 - self.h_min
        return self._y_grille() + max(0, heures) * H_HEURE

    # ------------------------------------------------------------------

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("white"))
        self._zones = []
        lj = self._largeur_jour()
        aujourdhui = date.today()
        y_grille = self._y_grille()
        bas = y_grille + (self.h_max - self.h_min) * H_HEURE

        # fonds de colonnes et en-têtes
        for i in range(7):
            jour = self.lundi + timedelta(days=i)
            x = L_HEURES + i * lj
            if jour == aujourdhui:
                p.fillRect(QRectF(x, 0, lj, bas), style.COULEUR_AUJOURDHUI)
            elif i >= 5:
                p.fillRect(QRectF(x, 0, lj, bas), style.COULEUR_WEEKEND)
            p.setFont(style.police(9.5, True))
            p.setPen(style.COULEUR_TEXTE)
            p.drawText(QRectF(x, 0, lj, H_ENTETE), Qt.AlignCenter, date_lisible(jour))

        # bandes journée (vie perso, expositions)
        for b in self.bandes:
            el = self.par_cle[b.cle]
            x0 = L_HEURES + (b.debut - self.lundi).days * lj + 2
            x1 = L_HEURES + ((b.fin - self.lundi).days + 1) * lj - 2
            r = QRectF(x0, H_ENTETE + b.piste * H_BANDE, x1 - x0, H_BANDE - 3)
            style.dessiner_fond(p, r, el, 3)
            texte = ("◂ " if b.coupe_gauche else "") + el.titre
            style.dessiner_texte(p, r.adjusted(0, 0, -12 if b.coupe_droite else 0, 0), texte, el, 8.5,
                                 gras=el.nature == "expo")
            if b.coupe_droite:
                p.setFont(style.police(8))
                p.setPen(style.COULEUR_TEXTE)
                p.drawText(r.adjusted(0, 0, -4, 0), Qt.AlignRight | Qt.AlignVCenter, "▸")
            self._contour(p, r, el)
            self._zones.append((r, el))

        # grille horaire
        p.setFont(style.police(8))
        for h in range(self.h_min, self.h_max + 1):
            y = y_grille + (h - self.h_min) * H_HEURE
            p.setPen(QPen(style.COULEUR_GRILLE))
            p.drawLine(QPointF(L_HEURES, y), QPointF(self.width(), y))
            if h < self.h_max:
                p.setPen(QPen(QColor("#EEEEEE"), 1, Qt.DotLine))
                p.drawLine(QPointF(L_HEURES, y + H_HEURE / 2), QPointF(self.width(), y + H_HEURE / 2))
                p.setPen(style.COULEUR_TEXTE_PALE)
                p.drawText(QRectF(0, y - 2, L_HEURES - 6, 16), Qt.AlignRight | Qt.AlignTop, f"{h:02d}:00")
        p.setPen(QPen(style.COULEUR_GRILLE))
        for i in range(8):
            x = L_HEURES + i * lj
            p.drawLine(QPointF(x, 0), QPointF(x, bas))

        # événements horaires
        for i in range(7):
            jour = self.lundi + timedelta(days=i)
            for el in self.horaires:
                if not (el.premier_jour <= jour <= el.dernier_jour):
                    continue
                col, n = self.places.get((el.cle, jour), (0, 1))
                debut, fin = self._bornes_jour(el, jour)
                y0 = self._y_heure(debut)
                y1 = max(self._y_heure(fin), y0 + H_HEURE / 2)
                largeur = (lj - 4) / n
                r = QRectF(L_HEURES + i * lj + 2 + col * largeur, y0 + 1, largeur - 2, y1 - y0 - 2)
                style.dessiner_fond(p, r, el, 4)
                self._texte_bloc(p, r, el)
                self._contour(p, r, el)
                self._zones.append((r, el))
        p.end()

    def _texte_bloc(self, p: QPainter, r: QRectF, el: Element) -> None:
        heure = f"{el.debut:%H:%M}–{el.fin:%H:%M}"
        src = el.source
        lignes = [heure, el.titre]
        if el.nature == "event":
            lieu = ", ".join(x for x in (src.get("venue"), src.get("city")) if x)
            lignes.append(" · ".join(x for x in (t("type_" + src["type"]), lieu) if x))
            if el.annule:
                lignes[0] += f"  ({t('statut_' + src['status'])})"
        elif el.nature == "perso":
            lignes.append(t("perso_type_" + src["type"]))
        style.dessiner_texte(p, r.adjusted(0, 2, 0, -2), "\n".join(lignes), el, 8, multiligne=True)

    def _contour(self, p: QPainter, r: QRectF, el: Element) -> None:
        if el.cle == self.selection:
            p.save()
            p.setPen(QPen(QColor("#1A1A1A"), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), 4, 4)
            p.restore()

    # ------------------------------------------------------------------

    def _trouver(self, pos: QPointF) -> Element | None:
        for rect, el in reversed(self._zones):
            if rect.contains(pos):
                return el
        return None

    def mousePressEvent(self, ev):
        el = self._trouver(ev.position())
        if el:
            self.selection = el.cle
            self.update()
            self.element_clique.emit(el)

    def mouseDoubleClickEvent(self, ev):
        pos = ev.position()
        if self._trouver(pos) or pos.x() < L_HEURES or pos.y() < self._y_grille():
            return
        i = min(6, int((pos.x() - L_HEURES) // self._largeur_jour()))
        heures = (pos.y() - self._y_grille()) / H_HEURE + self.h_min
        h, m = int(heures), 0 if (heures % 1) < 0.5 else 30
        self.creneau_double_clique.emit(datetime.combine(self.lundi + timedelta(days=i), time(min(h, 23), m)))

    def mouseMoveEvent(self, ev):
        el = self._trouver(ev.position())
        if el:
            self.setCursor(Qt.PointingHandCursor)
            QToolTip.showText(ev.globalPosition().toPoint(), el.titre, self)
        else:
            self.unsetCursor()
            QToolTip.hideText()
