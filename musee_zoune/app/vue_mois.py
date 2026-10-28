"""Vue mois (façon Google Agenda) : expositions en bandes continues, événements en pastilles."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .. import calendrier as cal
from .. import theme as th_mod
from ..textes import jour_court, nom_mois, t
from ..theme import SOMBRE, Theme
from . import style
from .donnees import Donnees, Element

H_ENTETE = 28       # noms des jours
H_NUMERO = 26       # numéro du jour dans chaque case
H_BANDE = 21
H_PASTILLE = 21
MAX_PASTILLES = 7
H_MIN_SEMAINE = 100
H_FINE = 5          # mode compact : bande d'exposition de 4 px + 1 px d'espace
H_MIN_COMPACT = 64


def disposition_semaine(n_perso: int, n_expos: int, n_ponctuels_max: int, compact: bool,
                        h_cible: float | None = None) -> tuple[float, int]:
    """Hauteur d'une semaine et nombre de lignes de pastilles disponibles.

    Mode normal : la semaine grandit pour tout montrer (jusqu'à MAX_PASTILLES).
    Mode compact : expositions en bandes fines et hauteur imposée (`h_cible`) pour que
    tout le mois tienne à l'écran ; ce qui ne rentre pas devient « +n autres ».
    """
    h_expo = H_FINE if compact else H_BANDE
    base = H_NUMERO + n_perso * H_BANDE + n_expos * h_expo + 6
    if compact and h_cible:
        hauteur = max(h_cible, H_MIN_COMPACT, base + H_PASTILLE)
        return hauteur, max(1, int((hauteur - base) // H_PASTILLE))
    lignes = min(n_ponctuels_max, MAX_PASTILLES + 1)
    return max(H_MIN_SEMAINE, base + lignes * H_PASTILLE), MAX_PASTILLES + 1


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


def en_bande(e: Element) -> bool:
    return e.journee and e.nature != "post"


class VueMois(QWidget):
    element_clique = Signal(object)        # Element
    jour_double_clique = Signal(object)    # date
    jour_choisi = Signal(object)           # date (clic sur « +n autres » ou le numéro)

    def __init__(self, donnees: Donnees, parent=None, theme: Theme = SOMBRE):
        super().__init__(parent)
        self.donnees = donnees
        self.theme = theme
        self.annee, self.mois = date.today().year, date.today().month
        self.selection: str | None = None
        self.compact = False
        self._h_cible: float | None = None
        self.hauteur_imposee: float | None = None  # export PDF : hauteur totale voulue
        self.lundis: list[date] = []
        self._zones: list[tuple[QRectF, object]] = []
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.recalculer()

    # ------------------------------------------------------------------

    def afficher_mois(self, annee: int, mois: int) -> None:
        self.annee, self.mois = annee, mois
        self.recalculer()

    def basculer_compact(self, compact: bool) -> None:
        self.compact = compact
        self.recalculer()

    def _hauteur_cible(self) -> float | None:
        """Hauteur d'une semaine pour que le mois remplisse la zone visible."""
        if not self.compact or not self.lundis:
            return None
        if self.hauteur_imposee:
            return float(int((self.hauteur_imposee - H_ENTETE - 4) / len(self.lundis)))
        zone = self.parentWidget()
        if zone is None:
            return None
        return float(int((zone.height() - H_ENTETE - 4) / len(self.lundis)))

    def recalculer(self) -> None:
        self.lundis = cal.semaines_du_mois(self.annee, self.mois)
        debut, fin = self.lundis[0], self.lundis[-1] + timedelta(days=6)
        self.elements = self.donnees.elements(debut, fin)
        self.semaines = []
        self._h_cible = self._hauteur_cible()
        for lundi in self.lundis:
            dimanche = lundi + timedelta(days=6)
            bandes_el = [e for e in self.elements if en_bande(e) and e.dernier_jour >= lundi
                         and e.premier_jour <= dimanche]
            par_cle = {e.cle: e for e in bandes_el}
            bandes = bandes_empilees(bandes_el, lundi)
            n_pistes = max((b.piste + 1 for b in bandes), default=0)
            jours = []
            for i in range(7):
                jour = lundi + timedelta(days=i)
                ponctuels = sorted(
                    (e for e in self.elements if not en_bande(e)
                     and e.premier_jour <= jour <= e.dernier_jour),
                    key=lambda e: (e.nature != "post", e.debut.time(), e.titre))
                jours.append(ponctuels)
            n_perso = max((b.piste + 1 for b in bandes if par_cle[b.cle].nature == "perso"), default=0)
            n_expos = n_pistes - n_perso
            hauteur, lignes = disposition_semaine(
                n_perso, n_expos, max((len(j) for j in jours), default=0), self.compact, self._h_cible)
            h_expo = H_FINE if self.compact else H_BANDE
            for b in bandes:  # position verticale de chaque bande dans la semaine
                if b.piste < n_perso:
                    b.y, b.h = b.piste * H_BANDE, H_BANDE - 2
                else:
                    b.y = n_perso * H_BANDE + (b.piste - n_perso) * h_expo
                    b.h = h_expo - (1 if self.compact else 2)
            self.semaines.append({"lundi": lundi, "bandes": bandes, "par_cle": par_cle,
                                  "h_bandes": n_perso * H_BANDE + n_expos * h_expo,
                                  "jours": jours, "hauteur": hauteur, "lignes": lignes})
        self.setMinimumHeight(int(H_ENTETE + sum(s["hauteur"] for s in self.semaines) + 2))
        self.update()

    # ------------------------------------------------------------------

    def _largeur_jour(self) -> float:
        return (self.width() - 1) / 7

    def paintEvent(self, _):
        th = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.fillRect(self.rect(), QColor(th.fond))
        self._zones = []
        lj = self._largeur_jour()
        grille = QPen(QColor(th.grille), 1)

        # en-têtes « LUN. », « MAR. »…
        p.setFont(style.police(8, poids=600))
        p.setPen(QColor(th.texte_secondaire))
        for i in range(7):
            p.drawText(QRectF(i * lj, 0, lj, H_ENTETE - 4), Qt.AlignHCenter | Qt.AlignBottom,
                       jour_court(i).upper())

        y = H_ENTETE
        aujourdhui = date.today()
        for sem in self.semaines:
            h = sem["hauteur"]
            p.setPen(grille)
            p.drawLine(QPointF(0, y), QPointF(self.width(), y))
            for i in range(7):
                jour = sem["lundi"] + timedelta(days=i)
                x = i * lj
                if i:
                    p.setPen(grille)
                    p.drawLine(QPointF(x, y), QPointF(x, y + h))
                self._numero(p, QRectF(x, y, lj, H_NUMERO), jour, aujourdhui)
                self._zones.append((QRectF(x, y, lj, H_NUMERO), ("jour", jour)))

            for b in sem["bandes"]:
                el: Element = sem["par_cle"][b.cle]
                x0 = (b.debut - sem["lundi"]).days * lj + (2 if b.coupe_gauche else 4)
                x1 = ((b.fin - sem["lundi"]).days + 1) * lj - (2 if b.coupe_droite else 4)
                r = QRectF(x0, y + H_NUMERO + b.y, x1 - x0, b.h)
                if self.compact and el.nature != "perso":
                    p.save()
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(el.couleur))
                    p.drawRoundedRect(r, 2, 2)
                    p.restore()
                    if el.cle == self.selection:
                        style.contour_selection(p, r, 2, th)
                    self._zones.append((r.adjusted(0, -1, 0, 1), el))
                    continue
                style.dessiner_fond(p, r, el, 4, th)
                place = style.dessiner_indicateur(p, r, el)
                titre = ("◂ " if b.coupe_gauche else "") + el.titre
                style.dessiner_texte(p, r.adjusted(0, 0, -place, 0), titre, el, 8.5,
                                     gras=el.nature == "expo", th=th)
                if el.cle == self.selection:
                    style.contour_selection(p, r, 4, th)
                self._zones.append((r, el))

            y0 = y + H_NUMERO + sem["h_bandes"] + 3
            lignes = sem["lignes"]
            for i, ponctuels in enumerate(sem["jours"]):
                jour = sem["lundi"] + timedelta(days=i)
                visibles = ponctuels if len(ponctuels) <= lignes else ponctuels[:lignes - 1]
                for k, el in enumerate(visibles):
                    r = QRectF(i * lj + 4, y0 + k * H_PASTILLE, lj - 8, H_PASTILLE - 3)
                    if el.nature == "post":
                        heure = "" if el.journee else el.debut.strftime("%H:%M  ")
                        style.dessiner_post(p, r, el, heure + el.titre, th)
                    else:
                        style.dessiner_fond(p, r, el, 4, th)
                        heure = el.debut.strftime("%H:%M") if el.debut.date() == jour else "…"
                        place = style.dessiner_indicateur(p, r, el)
                        style.dessiner_texte(p, r.adjusted(0, 0, -place, 0), f"{heure}  {el.titre}", el, 8.5, th=th)
                    if el.cle == self.selection:
                        style.contour_selection(p, r, 4, th)
                    self._zones.append((r, el))
                reste = len(ponctuels) - len(visibles)
                if reste:
                    r = QRectF(i * lj + 8, y0 + len(visibles) * H_PASTILLE, lj - 12, H_PASTILLE - 3)
                    p.setFont(style.police(8.5, poids=600))
                    p.setPen(QColor(th.texte))
                    p.drawText(r, Qt.AlignLeft | Qt.AlignVCenter, t("plus_n", n=reste))
                    self._zones.append((r, ("jour", jour)))
            y += h
        p.end()

    def _numero(self, p: QPainter, case: QRectF, jour: date, aujourdhui: date) -> None:
        th = self.theme
        texte = f"{jour.day}" if jour.day != 1 else f"1 {nom_mois(jour.month)}"
        p.setFont(style.police(8.5, poids=600 if jour == aujourdhui else 400))
        largeur = max(22, p.fontMetrics().horizontalAdvance(texte) + 12)
        zone = QRectF(case.left() + 5, case.top() + 3, largeur, 22)
        if jour == aujourdhui:
            p.save()
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(th_mod.COULEUR_ACCENT if th.sombre else "#1A73E8"))
            p.drawRoundedRect(zone, 11, 11)
            p.restore()
            p.setPen(QColor(th.aujourdhui_texte))
        else:
            p.setPen(QColor(th.texte if jour.month == self.mois else th.texte_attenue))
        p.drawText(zone, Qt.AlignCenter, texte)

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
        if isinstance(cible, Element):
            return
        jour = self._jour_sous(ev.position())
        if jour:
            self.jour_double_clique.emit(jour)

    def mouseMoveEvent(self, ev):
        cible = self._trouver(ev.position())
        if isinstance(cible, Element):
            self.setCursor(Qt.PointingHandCursor)
            QToolTip.showText(ev.globalPosition().toPoint(), cible.infobulle or cible.titre, self)
        elif isinstance(cible, tuple):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()
            QToolTip.hideText()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.compact and self._hauteur_cible() != self._h_cible:
            self.recalculer()
        self.update()

    def ajuster_a_la_zone(self) -> None:
        """Appelé quand la zone visible change de taille (mode compact)."""
        if self.compact:
            self.recalculer()
