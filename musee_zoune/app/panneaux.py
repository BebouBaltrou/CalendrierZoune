"""Panneau de droite : détails, changements récents, à poster, liste des posts."""

from __future__ import annotations

import html
from datetime import date, datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTextBrowser,
    QVBoxLayout, QWidget,
)

from .. import calendrier as cal
from .. import db
from .. import theme as th_mod
from ..textes import date_lisible, t
from .donnees import Donnees, Element, echeance, titre_post
from .style import icone, indicateur_icone, pastille

CSS_DETAILS = f"""
h3 {{ font-size: 15pt; font-weight: 400; margin: 0 0 8px 0; }}
a {{ color: {th_mod.COULEUR_ACCENT}; text-decoration: none; }}
.gris {{ color: #9AA0A6; }}
.champ {{ color: #9AA0A6; }}
"""


def periode_texte(debut: datetime, fin: datetime, journee: bool) -> str:
    if journee or fin.date() != debut.date():
        texte = date_lisible(debut.date(), longue=True)
        if fin.date() != debut.date():
            texte += " → " + date_lisible(fin.date(), longue=True)
        return texte if journee else f"{texte} ({debut:%H:%M}–{fin:%H:%M})"
    return f"{date_lisible(debut.date(), longue=True)}, {debut:%H:%M}–{fin:%H:%M}"


def texte_post(conn, post: dict, avec_liens: bool = True) -> str:
    jour = date_lisible(date.fromisoformat(post["date"][:10]), longue=True)
    lignes = [f"{titre_post(post)} — {jour} — {t('post_statut_' + post['statut'])}"]
    if avec_liens:
        n = len(post["evenements"])
        if n == 0:
            lignes.append(t("post_libre"))
        else:
            titres = [r[0] for r in conn.execute(
                f"SELECT title FROM events WHERE uid IN ({','.join('?' * n)}) ORDER BY start",
                post["evenements"])]
            lignes.append(t("post_couvre", n=n) + " : " + " · ".join(titres[:3]) + (" …" if n > 3 else ""))
    if post.get("note"):
        lignes.append(post["note"])
    return "\n".join(lignes)


# --------------------------------------------------------------------------

class Details(QWidget):
    modifier_perso = Signal(int)
    nouveau_post = Signal(object)        # dict d'événement à pré-cocher (ou None)
    modifier_post = Signal(int)
    posts_modifies = Signal()

    def __init__(self, donnees: Donnees, parent=None):
        super().__init__(parent)
        self.donnees = donnees
        self.element: Element | None = None
        self.texte = QTextBrowser()
        self.texte.setOpenExternalLinks(True)
        self.texte.document().setDefaultStyleSheet(CSS_DETAILS)
        self.bouton = QPushButton()
        self.bouton.clicked.connect(self._modifier_element)

        self.bloc_posts = QWidget()
        self.titre_posts = QLabel()
        self.titre_posts.setStyleSheet("font-weight:600; padding-top:6px;")
        self.liste_posts = QListWidget()
        self.liste_posts.setWordWrap(True)
        self.liste_posts.setMaximumHeight(190)
        self.liste_posts.setIconSize(QSize(14, 14))
        self.liste_posts.itemDoubleClicked.connect(lambda _i: self._modifier_post())
        self.btn_ajouter = QPushButton()
        self.btn_modifier = QPushButton()
        self.btn_supprimer = QPushButton()
        self.btn_ajouter.clicked.connect(lambda: self.nouveau_post.emit(self.element.source))
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
        layout.setContentsMargins(12, 8, 12, 12)
        layout.addWidget(self.texte, 1)
        layout.addWidget(self.bouton)
        layout.addWidget(self.bloc_posts)
        self.afficher(None)

    # -- posts liés à l'événement affiché --------------------------------------

    def _remplir_posts(self) -> None:
        self.titre_posts.setText(t("post_titre"))
        self.btn_ajouter.setText(t("post_ajouter"))
        self.btn_modifier.setText(t("details_modifier"))
        self.btn_supprimer.setText(t("post_supprimer"))
        self.liste_posts.clear()
        conn = self.donnees.conn
        posts = db.posts_de(conn, self.element.source["uid"]) if self.element else []
        if not posts:
            item = QListWidgetItem(indicateur_icone(None), t("post_aucun"))
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor(th_mod.COULEUR_SANS_POST))
            self.liste_posts.addItem(item)
        for post in posts:
            item = QListWidgetItem(indicateur_icone(post["statut"]), texte_post(conn, post))
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

    def _modifier_post(self) -> None:
        post = self._post_selectionne()
        if post:
            self.modifier_post.emit(post["id"])

    def _supprimer_post(self) -> None:
        post = self._post_selectionne()
        if post and confirmer_suppression_post(self, post):
            db.supprimer_post(self.donnees.conn, post["id"])
            self.rafraichir()
            self.posts_modifies.emit()

    def rafraichir(self) -> None:
        if self.element and self.element.nature in ("event", "expo"):
            self.element.etat_post = db.etat_posts(self.donnees.conn).get(self.element.source["uid"])
        self.afficher(self.element)

    def _modifier_element(self) -> None:
        if not self.element:
            return
        if self.element.nature == "perso":
            self.modifier_perso.emit(self.element.source["id"])
        elif self.element.nature == "post":
            self.modifier_post.emit(self.element.source["id"])

    # -- affichage ---------------------------------------------------------------

    def afficher(self, el: Element | None) -> None:
        self.element = el
        self.bouton.setText(t("details_modifier"))
        self.bouton.setVisible(bool(el and el.nature in ("perso", "post")))
        self.bloc_posts.setVisible(bool(el and el.nature in ("event", "expo")))
        if el and el.nature in ("event", "expo"):
            self._remplir_posts()
        if el is None:
            self.texte.setHtml(f"<p class='gris'>{html.escape(t('details_vide'))}</p>")
            return
        e = html.escape
        src = el.source
        quand = periode_texte(el.debut, el.fin, el.journee)
        pastille_html = (f"<span style='background:{el.couleur}'>&nbsp;&nbsp;&nbsp;&nbsp;</span>&nbsp; "
                         if el.nature in ("event", "expo") else "")
        lignes = [f"<h3>{pastille_html}{e(el.titre)}</h3>"]
        if el.nature == "perso":
            lignes.append(f"<p><span class='champ'>{e(t('details_type'))}</span> "
                          f"{e(t('perso_type_' + src['type']))}<br>"
                          f"<span class='champ'>{e(t('details_quand'))}</span> {e(quand)}</p>")
            if src.get("note"):
                lignes.append(f"<p>{e(src['note'])}</p>")
        elif el.nature == "post":
            lignes.append(f"<p>{e(texte_post(self.donnees.conn, src)).replace(chr(10), '<br>')}</p>")
        else:
            lieu = ", ".join(x for x in (src.get("venue"), src.get("address"), src.get("city")) if x)
            statut = t("statut_" + src["status"])
            couleur_statut = th_mod.COULEUR_ANNULE if src["status"] in ("annule", "reporte") \
                else th_mod.COULEUR_POST_PUBLIE
            lignes.append(
                f"<p>{e(quand)}<br>"
                f"<span class='gris'>{e(t('type_' + src['type']))} · {e(lieu or '—')}</span><br>"
                f"<span style='color:{couleur_statut}'>{e(statut)}</span></p>")
            if el.expo_liee and el.expo_liee in self.donnees.expos_par_uid:
                expo = self.donnees.expos_par_uid[el.expo_liee]
                couleur = self.donnees.couleur_expo(el.expo_liee)
                lignes.append(f"<p><span class='champ'>{e(t('details_expo_liee'))}</span><br>"
                              f"<span style='background:{couleur}'>&nbsp;&nbsp;&nbsp;</span> "
                              f"{e(expo['title'])}</p>")
            if src.get("description"):
                lignes.append(f"<p>{e(src['description'])}</p>")
            lignes.append(f"<p><a href='{e(src['url'])}'>{e(t('details_fiche'))} ↗</a></p>")
        self.texte.setHtml("".join(lignes))


def confirmer_suppression_post(parent, post: dict) -> bool:
    question = t("post_confirmer_suppr", reseau=t("reseau_" + post["reseau"]),
                 date=date.fromisoformat(post["date"][:10]).strftime("%d/%m/%Y"))
    return QMessageBox.question(parent, t("post_titre"), question) == QMessageBox.Yes


# --------------------------------------------------------------------------

class Changements(QWidget):
    """Changements depuis la dernière consultation (bouton « Marquer comme lu »)."""

    evenement_choisi = Signal(str)   # uid
    compteur_change = Signal(int)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.liste = QListWidget()
        self.liste.setWordWrap(True)
        self.liste.setIconSize(QSize(10, 10))
        self.liste.itemClicked.connect(self._clic)
        self.bouton = QPushButton()
        self.bouton.clicked.connect(self.marquer_lu)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
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
            item = QListWidgetItem(pastille(th_mod.COULEUR_CHANGEMENT.get(c["kind"], "#9AA0A6"), 10), texte)
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
        self.liste.setIconSize(QSize(14, 14))
        self.liste.itemClicked.connect(self._clic)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
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


class ListePosts(QWidget):
    """Tous les posts (liés ou libres), du plus récent au plus ancien."""

    nouveau_post = Signal(object)
    modifier_post = Signal(int)
    posts_modifies = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.liste = QListWidget()
        self.liste.setWordWrap(True)
        self.liste.setIconSize(QSize(14, 14))
        self.liste.itemDoubleClicked.connect(self._modifier)
        self.btn_nouveau = QPushButton()
        self.btn_nouveau.setIcon(icone("ajouter", "#202124", 16))
        self.btn_nouveau.setDefault(True)
        self.btn_nouveau.clicked.connect(lambda: self.nouveau_post.emit(None))
        self.btn_modifier = QPushButton()
        self.btn_modifier.clicked.connect(lambda: self._modifier(self.liste.currentItem()))
        self.btn_supprimer = QPushButton()
        self.btn_supprimer.clicked.connect(self._supprimer)
        boutons = QHBoxLayout()
        for b in (self.btn_nouveau, self.btn_modifier, self.btn_supprimer):
            boutons.addWidget(b)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.addWidget(self.liste)
        layout.addLayout(boutons)

    def remplir(self) -> None:
        self.btn_nouveau.setText(t("post_nouveau"))
        self.btn_modifier.setText(t("details_modifier"))
        self.btn_supprimer.setText(t("post_supprimer"))
        self.liste.clear()
        posts = db.tous_posts(self.conn)
        if not posts:
            item = QListWidgetItem(t("post_liste_vide"))
            item.setFlags(Qt.NoItemFlags)
            self.liste.addItem(item)
        for post in posts:
            item = QListWidgetItem(indicateur_icone(post["statut"]), texte_post(self.conn, post))
            item.setData(Qt.UserRole, post["id"])
            self.liste.addItem(item)

    def _modifier(self, item) -> None:
        if item and item.data(Qt.UserRole):
            self.modifier_post.emit(item.data(Qt.UserRole))

    def _supprimer(self) -> None:
        item = self.liste.currentItem()
        if not item or not item.data(Qt.UserRole):
            return
        post = db.lire_post(self.conn, item.data(Qt.UserRole))
        if post and confirmer_suppression_post(self, post):
            db.supprimer_post(self.conn, post["id"])
            self.remplir()
            self.posts_modifies.emit()
