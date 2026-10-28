"""Panneaux latéraux : légende, détails, changements récents."""

from __future__ import annotations

import html
from datetime import date, datetime, timedelta

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTextBrowser,
    QVBoxLayout, QWidget,
)

from .. import calendrier as cal
from .. import db
from ..textes import date_lisible, t
from .donnees import Donnees, Element, echeance


def pastille(couleur: str, perso: bool = False, taille: int = 14) -> QIcon:
    pix = QPixmap(taille, taille)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    if perso:
        p.setBrush(QColor(cal.COULEUR_PERSO_FOND))
        p.setPen(QPen(QColor(cal.COULEUR_PERSO), 1.2, Qt.DashLine))
        p.drawRoundedRect(1, 1, taille - 2, taille - 2, 3, 3)
        p.setBrush(QBrush(QColor(cal.COULEUR_PERSO).lighter(140), Qt.BDiagPattern))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(2, 2, taille - 4, taille - 4, 2, 2)
    else:
        p.setBrush(QColor(couleur))
        p.setPen(QPen(QColor(couleur).darker(130)))
        p.drawRoundedRect(1, 1, taille - 2, taille - 2, 3, 3)
    p.end()
    return QIcon(pix)


def indicateur_icone(etat: str | None) -> QIcon:
    """Petite icône reprenant l'indicateur de post des vues."""
    from . import style
    pix = QPixmap(14, 14)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    maintenant = datetime.now()
    faux = Element("x", "event", "", "#ffffff", maintenant, maintenant + timedelta(days=1),
                   False, etat_post=etat)
    style.dessiner_indicateur(p, QRectF(0, 0, 15, 14), faux)
    p.end()
    return QIcon(pix)


def periode_texte(debut: datetime, fin: datetime, journee: bool) -> str:
    if journee or fin.date() != debut.date():
        texte = date_lisible(debut.date(), longue=True)
        if fin.date() != debut.date():
            texte += " → " + date_lisible(fin.date(), longue=True)
        return texte if journee else f"{texte} ({debut:%H:%M}–{fin:%H:%M})"
    return f"{date_lisible(debut.date(), longue=True)}, {debut:%H:%M}–{fin:%H:%M}"


# --------------------------------------------------------------------------

class Legende(QWidget):
    """Couleurs des expositions ; un clic masque / affiche une exposition."""

    filtre_change = Signal()
    expo_choisie = Signal(str)

    def __init__(self, donnees: Donnees, parent=None):
        super().__init__(parent)
        self.donnees = donnees
        self.aide = QLabel()
        self.aide.setStyleSheet("color: #777; font-size: 11px;")
        self.liste = QListWidget()
        self.liste.setIconSize(QSize(14, 14))
        self.liste.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.liste.setTextElideMode(Qt.ElideRight)
        self.liste.itemChanged.connect(self._coche)
        self.liste.itemDoubleClicked.connect(self._double_clic)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.aide)
        layout.addWidget(self.liste)

    def remplir(self, debut, fin) -> None:
        self.aide.setText(t("legende_aide"))
        self.liste.blockSignals(True)
        self.liste.clear()
        for expo in self.donnees.expos_visibles(debut, fin):
            premier, dernier = cal.jours_de(expo)
            item = QListWidgetItem(pastille(self.donnees.couleur_expo(expo["uid"])), expo["title"])
            item.setToolTip(f"{expo['title']}\n{date_lisible(premier, True)} → {date_lisible(dernier, True)}"
                            f"\n{expo.get('venue') or ''} {expo.get('city') or ''}")
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            item.setCheckState(Qt.Unchecked if expo["uid"] in self.donnees.expos_masquees else Qt.Checked)
            item.setData(Qt.UserRole, expo["uid"])
            self.liste.addItem(item)
        for icone, texte in ((pastille(cal.COULEURS_TYPES["atelier"]), t("legende_autres")),
                             (pastille("", perso=True), t("legende_vie_perso")),
                             (indicateur_icone(None), t("legende_sans_post")),
                             (indicateur_icone("prevu"), t("legende_post_prevu")),
                             (indicateur_icone("publie"), t("legende_post_publie"))):
            item = QListWidgetItem(icone, texte)
            item.setFlags(Qt.ItemIsEnabled)
            item.setForeground(QColor("#555"))
            self.liste.addItem(item)
        self.liste.blockSignals(False)

    def _coche(self, item: QListWidgetItem) -> None:
        uid = item.data(Qt.UserRole)
        if not uid:
            return
        if item.checkState() == Qt.Checked:
            self.donnees.expos_masquees.discard(uid)
        else:
            self.donnees.expos_masquees.add(uid)
        self.filtre_change.emit()

    def _double_clic(self, item: QListWidgetItem) -> None:
        if item.data(Qt.UserRole):
            self.expo_choisie.emit(item.data(Qt.UserRole))


# --------------------------------------------------------------------------

class Details(QWidget):
    modifier_perso = Signal(int)
    posts_modifies = Signal()

    def __init__(self, donnees: Donnees, parent=None):
        super().__init__(parent)
        self.donnees = donnees
        self.element: Element | None = None
        self.texte = QTextBrowser()
        self.texte.setOpenExternalLinks(True)
        self.bouton = QPushButton()
        self.bouton.clicked.connect(lambda: self.modifier_perso.emit(self.element.source["id"]))

        # section « Posts »
        self.bloc_posts = QWidget()
        self.titre_posts = QLabel()
        self.titre_posts.setStyleSheet("font-weight:bold; margin-top:4px;")
        self.liste_posts = QListWidget()
        self.liste_posts.setMaximumHeight(160)
        self.liste_posts.setWordWrap(True)
        self.liste_posts.setIconSize(QSize(12, 12))
        self.liste_posts.itemDoubleClicked.connect(lambda _i: self._modifier_post())
        self.btn_ajouter = QPushButton()
        self.btn_modifier = QPushButton()
        self.btn_supprimer = QPushButton()
        self.btn_ajouter.clicked.connect(self._ajouter_post)
        self.btn_modifier.clicked.connect(self._modifier_post)
        self.btn_supprimer.clicked.connect(self._supprimer_post)
        ligne = QHBoxLayout()
        for b in (self.btn_ajouter, self.btn_modifier, self.btn_supprimer):
            ligne.addWidget(b)
        bloc = QVBoxLayout(self.bloc_posts)
        bloc.setContentsMargins(0, 0, 0, 0)
        bloc.addWidget(self.titre_posts)
        bloc.addWidget(self.liste_posts)
        bloc.addLayout(ligne)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.texte, 1)
        layout.addWidget(self.bouton)
        layout.addWidget(self.bloc_posts)
        self.afficher(None)

    # -- posts ------------------------------------------------------------

    def _remplir_posts(self) -> None:
        self.titre_posts.setText(t("post_titre"))
        self.btn_ajouter.setText(t("post_ajouter"))
        self.btn_modifier.setText(t("details_modifier"))
        self.btn_supprimer.setText(t("post_supprimer"))
        self.liste_posts.clear()
        posts = db.posts_de(self.donnees.conn, self.element.source["uid"]) if self.element else []
        if not posts:
            item = QListWidgetItem(indicateur_icone(None), t("post_aucun"))
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor("#C04A00"))
            self.liste_posts.addItem(item)
        for post in posts:
            jour = date_lisible(date.fromisoformat(post["date"][:10]), longue=True)
            texte = f"{t('reseau_' + post['reseau'])} — {jour} — {t('post_statut_' + post['statut'])}"
            if post["note"]:
                texte += "\n" + post["note"]
            item = QListWidgetItem(indicateur_icone(post["statut"]), texte)
            item.setData(Qt.UserRole, post["id"])
            self.liste_posts.addItem(item)
        if posts:
            self.liste_posts.setCurrentRow(0)
        self.btn_modifier.setEnabled(bool(posts))
        self.btn_supprimer.setEnabled(bool(posts))

    def _post_selectionne(self) -> dict | None:
        item = self.liste_posts.currentItem()
        if item is None or item.data(Qt.UserRole) is None:
            return None
        return db.lire_post(self.donnees.conn, item.data(Qt.UserRole))

    def _ajouter_post(self) -> None:
        from .dialogues import DialoguePost
        if DialoguePost(self.donnees.conn, self, event=self.element.source).exec():
            self._apres_modif_posts()

    def _modifier_post(self) -> None:
        from .dialogues import DialoguePost
        post = self._post_selectionne()
        if post and DialoguePost(self.donnees.conn, self, event=self.element.source, post=post).exec():
            self._apres_modif_posts()

    def _supprimer_post(self) -> None:
        post = self._post_selectionne()
        if not post:
            return
        question = t("post_confirmer_suppr", reseau=t("reseau_" + post["reseau"]),
                     date=date.fromisoformat(post["date"][:10]).strftime("%d/%m/%Y"))
        if QMessageBox.question(self, t("post_titre"), question) == QMessageBox.Yes:
            db.supprimer_post(self.donnees.conn, post["id"])
            self._apres_modif_posts()

    def _apres_modif_posts(self) -> None:
        self.element.etat_post = db.etat_posts(self.donnees.conn).get(self.element.source["uid"])
        self._remplir_posts()
        self.posts_modifies.emit()

    # -- affichage ----------------------------------------------------------

    def afficher(self, el: Element | None) -> None:
        self.element = el
        self.bouton.setText(t("details_modifier"))
        self.bouton.setVisible(bool(el and el.nature == "perso"))
        self.bloc_posts.setVisible(bool(el and el.nature != "perso"))
        if el and el.nature != "perso":
            self._remplir_posts()
        if el is None:
            self.texte.setHtml(f"<p style='color:#777'>{html.escape(t('details_vide'))}</p>")
            return
        e = html.escape
        src = el.source
        quand = periode_texte(el.debut, el.fin, el.journee)
        lignes = [f"<h3 style='margin-bottom:4px'>{e(el.titre)}</h3>"]
        if el.nature == "perso":
            lignes.append(f"<p><b>{e(t('details_type'))}</b> : {e(t('perso_type_' + src['type']))}<br>"
                          f"<b>{e(t('details_quand'))}</b> : {e(quand)}</p>")
            if src.get("note"):
                lignes.append(f"<p>{e(src['note'])}</p>")
        else:
            lieu = ", ".join(x for x in (src.get("venue"), src.get("address"), src.get("city")) if x)
            statut = t("statut_" + src["status"])
            couleur_statut = "#B00020" if src["status"] in ("annule", "reporte") else "#2E7D32"
            lignes.append(
                f"<p><b>{e(t('details_type'))}</b> : {e(t('type_' + src['type']))}<br>"
                f"<b>{e(t('details_quand'))}</b> : {e(quand)}<br>"
                f"<b>{e(t('details_lieu'))}</b> : {e(lieu or '—')}<br>"
                f"<b>{e(t('details_statut'))}</b> : <span style='color:{couleur_statut}'>{e(statut)}</span></p>")
            if el.expo_liee and el.expo_liee in self.donnees.expos_par_uid:
                expo = self.donnees.expos_par_uid[el.expo_liee]
                couleur = self.donnees.couleur_expo(el.expo_liee)
                lignes.append(f"<p><b>{e(t('details_expo_liee'))}</b> : "
                              f"<span style='background:{couleur}'>&nbsp;&nbsp;&nbsp;</span> {e(expo['title'])}</p>")
            if src.get("description"):
                lignes.append(f"<p>{e(src['description'])}</p>")
            lignes.append(f"<p><a href='{e(src['url'])}'>{e(t('details_fiche'))}</a></p>")
        self.texte.setHtml("".join(lignes))


# --------------------------------------------------------------------------

ICONES_CHG = {"ajout": "#2E7D32", "modification": "#E08E0B", "annulation": "#B00020"}


class Changements(QWidget):
    """Changements depuis la dernière consultation (bouton « Marquer comme lu »)."""

    evenement_choisi = Signal(str)   # uid
    compteur_change = Signal(int)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.liste = QListWidget()
        self.liste.setWordWrap(True)
        self.liste.itemClicked.connect(self._clic)
        self.bouton = QPushButton()
        self.bouton.clicked.connect(self.marquer_lu)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.liste)
        layout.addWidget(self.bouton)

    def vu_jusqua(self) -> int:
        return int(db.lire_reglage(self.conn, "dernier_changement_vu", "0"))

    def remplir(self) -> None:
        self.bouton.setText(t("chg_marquer_lu"))
        self.liste.clear()
        changements = db.changements_depuis(self.conn, self.vu_jusqua())
        if not changements:
            item = QListWidgetItem(t("chg_aucun"))
            item.setFlags(Qt.NoItemFlags)
            self.liste.addItem(item)
        for c in changements:
            quand = periode_texte(cal.dt(c["start"]), cal.dt(c["end"] or c["start"]), c["type"] == "exposition")
            texte = f"{t('chg_' + c['kind'])} — {c['title']}\n{quand}"
            details = c["details"]
            if c["kind"] == "modification":
                champs = [t("champ_" + k) for k in details if k != "motif"]
                if champs:
                    texte += "\n" + ", ".join(champs)
            if details.get("motif"):
                texte += f"\n({details['motif']})"
            texte += "  · " + t("chg_le", date=cal.dt(c["at"]).strftime("%d/%m %H:%M"))
            item = QListWidgetItem(pastille(ICONES_CHG.get(c["kind"], "#999"), taille=12), texte)
            item.setData(Qt.UserRole, c["event_uid"])
            self.liste.addItem(item)
        self.bouton.setEnabled(bool(changements))
        self.compteur_change.emit(len(changements))

    def marquer_lu(self) -> None:
        db.ecrire_reglage(self.conn, "dernier_changement_vu", str(db.dernier_changement_id(self.conn)))
        self.remplir()

    def _clic(self, item: QListWidgetItem) -> None:
        if item.data(Qt.UserRole):
            self.evenement_choisi.emit(item.data(Qt.UserRole))


# --------------------------------------------------------------------------

class APoster(QWidget):
    """Rappel J-7 : événements des 7 prochains jours sans aucun post."""

    evenement_choisi = Signal(str)
    compteur_change = Signal(int)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.evenements: list[dict] = []
        self.liste = QListWidget()
        self.liste.setWordWrap(True)
        self.liste.setIconSize(QSize(12, 12))
        self.liste.itemClicked.connect(self._clic)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.liste)

    def remplir(self) -> None:
        aujourdhui = date.today()
        self.evenements = db.a_poster(self.conn, aujourdhui)
        self.liste.clear()
        if not self.evenements:
            item = QListWidgetItem(t("aposter_vide"))
            item.setFlags(Qt.NoItemFlags)
            self.liste.addItem(item)
        for ev in self.evenements:
            debut = cal.dt(ev["start"])
            texte = (f"{ev['title']}\n{date_lisible(debut.date())}, {debut:%H:%M} — "
                     f"{echeance(debut.date(), aujourdhui)}")
            lieu = ", ".join(x for x in (ev.get("venue"), ev.get("city")) if x)
            if lieu:
                texte += f" — {lieu}"
            item = QListWidgetItem(indicateur_icone(None), texte)
            item.setData(Qt.UserRole, ev["uid"])
            self.liste.addItem(item)
        self.compteur_change.emit(len(self.evenements))

    def _clic(self, item: QListWidgetItem) -> None:
        if item.data(Qt.UserRole):
            self.evenement_choisi.emit(item.data(Qt.UserRole))
