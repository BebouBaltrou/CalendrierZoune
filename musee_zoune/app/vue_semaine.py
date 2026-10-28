"""Vue semaine (façon Google Agenda) : journées entières en haut, créneaux horaires dessous."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .. import calendrier as cal
from .. import theme as th_mod
from ..textes import jour_court, t
from ..theme import SOMBRE, Theme
from . import style
from .donnees import Donnees, Element
from .vue_mois import bandes_empilees

L_HEURES = 60       # colonne des heures
H_ENTETE = 74       # « LUN. » + grand numéro
H_BANDE = 22
H_HEURE = 60        # hauteur d'une heure
HEURE_MIN, HEURE_MAX = 8, 21  # plage par défaut, élargie si besoin
ROUGE_MAINTENANT = "#EA4335"


class VueSemaine(QWidget):
    element_clique = Signal(object)
    creneau_double_clique = Signal(object)  # datetime

    def __init__(self, donnees: Donnees, parent=None, theme: Theme = SOMBRE):
        super().__init__(parent)
        self.donnees = donnees
        self.theme = theme
        self.lundi = cal.lundi_de(date.today())
        self.selection: str | None = None
        self.h_min, self.h_max = HEURE_MIN, HEURE_MAX
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
        self.h_max = min(24, max([HEURE_MAX] + heures))

        # colonnes côte à côte, jour par jour
        self.places: dict = {}
        for i in range(7):
            jour = self.lundi + timedelta(days=i)
            du_jour = [(e.cle, *self._bornes_jour(e, jour)) for e in self.horaires
                       if e.premier_jour <= jour <= e.dernier_jour]
            for cle, place in cal.colonnes(du_jour).items():
                self.places[(cle, jour)] = place
        self.setMinimumHeight(int(self._y_grille() + (self.h_max - self.h_min) * H_HEURE + 8))
        self.update()

    def _bornes_jour(self, e: Element, jour: date) -> tuple[datetime, datetime]:
        debut = max(e.debut, datetime.combine(jour, time(self.h_min)))
        fin = min(e.fin, datetime.combine(jour, time(23, 59)))
        return debut, fin

    def _y_grille(self) -> float:
        return H_ENTETE + self.n_pistes * H_BANDE + 10

    def _largeur_jour(self) -> float:
        return (self.width() - L_HEURES - 1) / 7

    def _y_heure(self, moment: datetime) -> float:
        heures = moment.hour + moment.minute / 60 - self.h_min
        return self._y_grille() + max(0, heures) * H_HEURE

    # ------------------------------------------------------------------

    def paintEvent(self, _):
        th = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.fillRect(self.rect(), QColor(th.fond))
        self._zones = []
        lj = self._largeur_jour()
        aujourdhui = date.today()
        y_grille = self._y_grille()
        bas = y_grille + (self.h_max - self.h_min) * H_HEURE
        grille = QPen(QColor(th.grille), 1)
        accent = QColor(th_mod.COULEUR_ACCENT if th.sombre else "#1A73E8")

        # en-têtes : « LUN. » puis grand numéro (rond bleu pour aujourd'hui)
        for i in range(7):
            jour = self.lundi + timedelta(days=i)
            x = L_HEURES + i * lj
            courant = jour == aujourdhui
            p.setFont(style.police(8, poids=600))
            p.setPen(accent if courant else QColor(th.texte_secondaire))
            p.drawText(QRectF(x, 6, lj, 18), Qt.AlignCenter, jour_court(i).upper())
            cercle = QRectF(x + lj / 2 - 22, 26, 44, 44)
            if courant:
                p.save()
                p.setPen(Qt.NoPen)
                p.setBrush(accent)
                p.drawEllipse(cercle)
                p.restore()
            p.setFont(style.police(18, poids=400))
            p.setPen(QColor(th.aujourdhui_texte if courant else th.texte))
            p.drawText(cercle, Qt.AlignCenter, str(jour.day))

        # séparateurs de colonnes (sous les bandes)
        p.setPen(grille)
        for i in range(8):
            x = L_HEURES + i * lj
            p.drawLine(QPointF(x, H_ENTETE - 4 if i else y_grille), QPointF(x, bas))

        # bandes journée (vie perso, expositions, posts libres)
        for b in self.bandes:
            el = self.par_cle[b.cle]
            x0 = L_HEURES + (b.debut - self.lundi).days * lj + 3
            x1 = L_HEURES + ((b.fin - self.lundi).days + 1) * lj - 3
            r = QRectF(x0, H_ENTETE + b.piste * H_BANDE, x1 - x0, H_BANDE - 3)
            style.dessiner_fond(p, r, el, 4, th)
            texte = ("◂ " if b.coupe_gauche else "") + ("✎ " if el.nature == "post" else "") + el.titre
            place = style.dessiner_indicateur(p, r, el)
            style.dessiner_texte(p, r.adjusted(0, 0, -place, 0), texte, el, 8.5,
                                 gras=el.nature == "expo", th=th)
            if el.cle == self.selection:
                style.contour_selection(p, r, 4, th)
            self._zones.append((r, el))

        # grille horaire
        p.setPen(grille)
        p.drawLine(QPointF(L_HEURES, y_grille), QPointF(self.width(), y_grille))
        p.setFont(style.police(8))
        for h in range(self.h_min, self.h_max + 1):
            y = y_grille + (h - self.h_min) * H_HEURE
            p.setPen(grille)
            p.drawLine(QPointF(L_HEURES - 6, y), QPointF(self.width(), y))
            if h > self.h_min:
                p.setPen(QColor(th.texte_secondaire))
                p.drawText(QRectF(0, y - 8, L_HEURES - 12, 16), Qt.AlignRight | Qt.AlignVCenter,
                           f"{h:02d}:00")
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
                largeur = (lj - 8) / n
                r = QRectF(L_HEURES + i * lj + 2 + col * largeur, y0 + 1, largeur - 2, y1 - y0 - 2)
                style.dessiner_fond(p, r, el, 6, th)
                place = style.dessiner_indicateur(p, r, el, en_haut=True)
                self._texte_bloc(p, r.adjusted(0, 0, -place, 0), el)
                if el.cle == self.selection:
                    style.contour_selection(p, r, 6, th)
                self._zones.append((r, el))

        # ligne rouge de l'heure actuelle
        maintenant = datetime.now()
        if self.lundi <= maintenant.date() <= self.lundi + timedelta(days=6) \
                and self.h_min <= maintenant.hour < self.h_max:
            i = (maintenant.date() - self.lundi).days
            y = self._y_heure(maintenant)
            x0 = L_HEURES + i * lj
            p.setPen(QPen(QColor(ROUGE_MAINTENANT), 2))
            p.drawLine(QPointF(x0, y), QPointF(x0 + lj, y))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ROUGE_MAINTENANT))
            p.drawEllipse(QPointF(x0, y), 6, 6)
        p.end()

    def _texte_bloc(self, p: QPainter, r: QRectF, el: Element) -> None:
        src = el.source
        if r.width() < 95:  # bloc étroit (événements simultanés) : titre puis heure, sans coupure de mots
            p.save()
            p.setFont(style.police(8))
            p.setPen(style.couleur_texte(el, self.theme))
            m = p.fontMetrics()
            zone = r.adjusted(5, 4, -3, -2)
            y = zone.top()
            for ligne in (el.titre, f"{el.debut:%H:%M}"):
                if y + m.height() > zone.bottom() + 2:
                    break
                p.drawText(QRectF(zone.left(), y, zone.width(), m.height()), Qt.AlignLeft | Qt.AlignTop,
                           m.elidedText(ligne, Qt.ElideRight, int(zone.width())))
                y += m.height()
            p.restore()
            return
        lignes = [el.titre, f"{el.debut:%H:%M} – {el.fin:%H:%M}"]
        if el.nature == "event":
            lieu = ", ".join(x for x in (src.get("venue"), src.get("city")) if x)
            lignes.append(" · ".join(x for x in (t("type_" + src["type"]), lieu) if x))
            if el.annule:
                lignes[1] += f"  ({t('statut_' + src['status'])})"
        elif el.nature == "perso":
            lignes.append(t("perso_type_" + src["type"]))
        style.dessiner_texte(p, r.adjusted(0, 4, 0, -2), "\n".join(lignes), el, 8.5,
                             multiligne=True, th=self.theme)

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
