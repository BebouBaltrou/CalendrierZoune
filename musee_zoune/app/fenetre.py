"""Fenêtre principale de Musée Zoune (habillage façon Google Agenda, thème sombre)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from PySide6.QtCore import QPoint, QSize, Qt, QThread, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QSystemTrayIcon, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from .. import db, textes
from .. import theme as th_mod
from ..sync import derniere_sync, lancer_sync, sync_necessaire
from ..textes import date_lisible, nom_mois, t
from . import style
from .barre_laterale import BarreLaterale
from .dialogues import DialoguePerso, DialoguePost, ListePerso
from .donnees import Donnees, Element, noter_notification, notification_a_faire
from .panneaux import APoster, Changements, Details, ListePosts
from .vue_mois import VueMois
from .vue_semaine import VueSemaine

log = logging.getLogger("musee_zoune.app")
GRIS = "#9AA0A6"
CLAIR = "#E8EAED"


class ZoneDefilement(QScrollArea):
    """Zone de défilement qui prévient quand sa taille change (mode compact)."""

    redimensionnee = Signal()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.redimensionnee.emit()


class FilSync(QThread):
    """Synchronisation en arrière-plan : l'interface reste utilisable."""

    termine = Signal(object)   # résumé (dict) ou None si déjà faite aujourd'hui
    echec = Signal(str)

    def __init__(self, forcer: bool, parent=None):
        super().__init__(parent)
        self.forcer = forcer

    def run(self):
        try:
            self.termine.emit(lancer_sync(forcer=self.forcer, afficher=lambda _texte: None))
        except Exception as exc:  # noqa: BLE001 — pas d'internet, site en panne…
            log.warning("synchronisation impossible : %s", exc)
            self.echec.emit(str(exc))


def bouton_icone(nom: str, aide: str = "", taille: int = 20, checkable: bool = False) -> QToolButton:
    b = QToolButton()
    b.setIcon(style.icone(nom, CLAIR, taille))
    b.setIconSize(QSize(taille, taille))
    b.setToolTip(aide)
    b.setCheckable(checkable)
    b.setFixedSize(40, 40)
    b.setStyleSheet("QToolButton { border-radius: 20px; padding: 0; }")
    return b


def logo(taille: int = 36) -> QPixmap:
    pix = QPixmap(taille * 2, taille * 2)
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(th_mod.COULEUR_ACCENT))
    p.drawRoundedRect(2, 4, taille - 4, taille - 6, 6, 6)
    p.setBrush(QColor("#1A73E8"))
    p.drawRoundedRect(2, 4, taille - 4, 9, 4, 4)
    p.drawRect(2, 9, taille - 4, 4)
    p.setPen(QColor("#202124"))
    f = style.police(10, True)
    f.setPixelSize(int(taille * 0.42))
    p.setFont(f)
    p.drawText(0, 12, taille, taille - 12, Qt.AlignCenter, str(date.today().day))
    p.end()
    return pix


class FenetrePrincipale(QMainWindow):
    def __init__(self, conn, synchroniser_au_demarrage: bool = True):
        super().__init__()
        self.conn = conn
        textes.choisir_langue(db.lire_reglage(conn, "langue", "fr"))
        self.donnees = Donnees(conn)
        self.jour = date.today()
        self.fil: FilSync | None = None
        self.resize(1440, 900)
        self.setWindowIcon(QIcon(logo(64)))

        self._barre_haut()
        self.laterale = BarreLaterale(self.donnees)
        self.laterale.date_choisie.connect(self.aller_a)
        self.laterale.filtres_changes.connect(self._rafraichir_vues)

        # vues
        self.vue_mois = VueMois(self.donnees)
        self.vue_semaine = VueSemaine(self.donnees)
        self.pile = QStackedWidget()
        for vue in (self.vue_mois, self.vue_semaine):
            zone = ZoneDefilement()
            zone.setWidgetResizable(True)
            zone.setWidget(vue)
            zone.setFrameShape(QScrollArea.NoFrame)
            self.pile.addWidget(zone)
        self.pile.widget(0).redimensionnee.connect(self.vue_mois.ajuster_a_la_zone)
        self.vue_mois.compact = db.lire_reglage(conn, "mois_compact", "0") == "1"
        self.act_compact.setChecked(self.vue_mois.compact)

        # panneau de droite (détails, changements, à poster, posts)
        self.details = Details(self.donnees)
        self.changements = Changements(conn)
        self.aposter = APoster(conn)
        self.liste_posts = ListePosts(conn)
        self.onglets = QTabWidget()
        self.onglets.setDocumentMode(True)
        for w in (self.details, self.changements, self.aposter, self.liste_posts):
            self.onglets.addTab(w, "")
        self.titre_panneau = QLabel()
        self.titre_panneau.setStyleSheet("font-size: 11pt; padding-left: 12px;")
        fermer = bouton_icone("fermer", "", 16)
        fermer.clicked.connect(lambda: self.panneau.hide())
        self.btn_fermer_panneau = fermer
        entete = QHBoxLayout()
        entete.setContentsMargins(4, 8, 8, 0)
        entete.addWidget(self.titre_panneau, 1)
        entete.addWidget(fermer)
        self.panneau = QFrame()
        self.panneau.setFixedWidth(400)
        self.panneau.setStyleSheet(f"QFrame#panneau {{ border-left: 1px solid {th_mod.SOMBRE.grille}; }}")
        self.panneau.setObjectName("panneau")
        couche = QVBoxLayout(self.panneau)
        couche.setContentsMargins(0, 0, 0, 0)
        couche.addLayout(entete)
        couche.addWidget(self.onglets)
        self.panneau.hide()

        # titre de période au-dessus de la grille (affiché dans la barre du haut)
        centre = QWidget()
        lignes = QHBoxLayout(centre)
        lignes.setContentsMargins(0, 0, 0, 0)
        lignes.setSpacing(0)
        lignes.addWidget(self.laterale)
        cadre_vue = QWidget()
        couche_vue = QVBoxLayout(cadre_vue)
        couche_vue.setContentsMargins(0, 0, 16, 0)
        couche_vue.addWidget(self.pile)
        lignes.addWidget(cadre_vue, 1)
        lignes.addWidget(self.panneau)
        racine = QWidget()
        pile_racine = QVBoxLayout(racine)
        pile_racine.setContentsMargins(0, 0, 0, 0)
        pile_racine.setSpacing(0)
        pile_racine.addWidget(self.barre)
        pile_racine.addWidget(centre, 1)
        self.setCentralWidget(racine)

        # bouton « + » flottant
        self.fab = QPushButton(cadre_vue)
        self.fab.setIcon(style.icone("ajouter", "#202124", 26))
        self.fab.setIconSize(QSize(26, 26))
        self.fab.setFixedSize(60, 60)
        self.fab.setCursor(Qt.PointingHandCursor)
        self.fab.setStyleSheet(
            f"QPushButton {{ background: {th_mod.COULEUR_FAB}; border: none; border-radius: 30px; }}"
            f"QPushButton:hover {{ background: #F6AEA9; }}")
        self.menu_fab = QMenu(self)
        self.act_fab_perso = self.menu_fab.addAction("", lambda: self._nouveau_perso(
            datetime.combine(self.jour, datetime.min.time()), True))
        self.act_fab_post = self.menu_fab.addAction("", lambda: self.nouveau_post(self._evenement_selectionne()))
        self.fab.clicked.connect(lambda: self.menu_fab.exec(
            self.fab.mapToGlobal(QPoint(-self.menu_fab.sizeHint().width() + 60, -self.menu_fab.sizeHint().height() - 6))))
        cadre_vue.installEventFilter(self)
        self.cadre_vue = cadre_vue

        # signaux
        for vue in (self.vue_mois, self.vue_semaine):
            vue.element_clique.connect(self._element_clique)
        self.vue_mois.jour_double_clique.connect(
            lambda j: self._nouveau_perso(datetime.combine(j, datetime.min.time()), True))
        self.vue_mois.jour_choisi.connect(self._aller_semaine)
        self.vue_semaine.creneau_double_clique.connect(lambda m: self._nouveau_perso(m, False))
        self.details.modifier_perso.connect(self._modifier_perso)
        self.details.nouveau_post.connect(self.nouveau_post)
        self.details.modifier_post.connect(self.modifier_post)
        self.details.posts_modifies.connect(self._posts_modifies)
        self.changements.evenement_choisi.connect(self._evenement_choisi)
        self.changements.compteur_change.connect(lambda _n: self._badges())
        self.aposter.evenement_choisi.connect(self._evenement_choisi)
        self.aposter.compteur_change.connect(lambda _n: self._badges())
        self.liste_posts.nouveau_post.connect(self.nouveau_post)
        self.liste_posts.modifier_post.connect(self.modifier_post)
        self.liste_posts.posts_modifies.connect(self._posts_modifies)
        self.icone_notif = self._icone_notification()

        self._barre_defilement_mois()
        self.retraduire()
        self._etat_sync_initial()
        self.aposter.remplir()
        self.liste_posts.remplir()
        if synchroniser_au_demarrage and sync_necessaire(conn):
            self.synchroniser(forcer=False)  # le rappel sera notifié après la synchro
        elif synchroniser_au_demarrage:
            self.notifier_a_poster()

    # ------------------------------------------------------------------ barre du haut

    def _barre_haut(self) -> None:
        self.barre = QWidget()
        self.barre.setFixedHeight(64)
        self.barre.setObjectName("barre")
        self.barre.setAttribute(Qt.WA_StyledBackground, True)
        self.barre.setStyleSheet(f"QWidget#barre {{ border-bottom: 1px solid {th_mod.SOMBRE.grille}; }}")
        b = QHBoxLayout(self.barre)
        b.setContentsMargins(8, 8, 12, 8)
        b.setSpacing(4)

        self.btn_menu = bouton_icone("menu")
        self.btn_menu.clicked.connect(lambda: self.laterale.setVisible(not self.laterale.isVisible()))
        icone_logo = QLabel()
        icone_logo.setPixmap(logo(36))
        icone_logo.setStyleSheet("padding-left: 6px;")
        self.nom_app = QLabel()
        self.nom_app.setStyleSheet("font-size: 16pt; color: #E8EAED; padding: 0 28px 0 6px;")
        self.btn_auj = QPushButton()
        self.btn_auj.setCursor(Qt.PointingHandCursor)
        self.btn_auj.setFixedHeight(36)
        self.btn_auj.clicked.connect(self._aujourdhui)
        self.btn_prec = bouton_icone("precedent", "", 16)
        self.btn_suiv = bouton_icone("suivant", "", 16)
        self.btn_prec.clicked.connect(lambda: self._deplacer(-1))
        self.btn_suiv.clicked.connect(lambda: self._deplacer(1))
        self.titre_periode = QLabel()
        self.titre_periode.setStyleSheet("font-size: 17pt; color: #E8EAED; padding-left: 10px;")
        for w in (self.btn_menu, icone_logo, self.nom_app, self.btn_auj):
            b.addWidget(w)
        b.addSpacing(10)
        for w in (self.btn_prec, self.btn_suiv, self.titre_periode):
            b.addWidget(w)
        b.addStretch(1)

        self.recherche = QLineEdit()
        self.recherche.setClearButtonEnabled(True)
        self.recherche.addAction(style.icone("recherche", GRIS, 18), QLineEdit.LeadingPosition)
        self.recherche.setFixedWidth(260)
        self.recherche.setStyleSheet("QLineEdit { border-radius: 18px; padding: 7px 10px; }")
        self.recherche.textChanged.connect(self._rechercher)
        b.addWidget(self.recherche)
        b.addSpacing(6)

        self.btn_vue = QToolButton()
        self.btn_vue.setPopupMode(QToolButton.InstantPopup)
        self.btn_vue.setStyleSheet(f"QToolButton {{ border: 1px solid {th_mod.SOMBRE.grille}; "
                                   "border-radius: 18px; padding: 7px 16px; }")
        self.menu_vue = QMenu(self)
        groupe = QActionGroup(self)
        self.act_mois = QAction(self, checkable=True)
        self.act_semaine = QAction(self, checkable=True)
        for i, act in enumerate((self.act_mois, self.act_semaine)):
            groupe.addAction(act)
            self.menu_vue.addAction(act)
            act.triggered.connect(lambda _=False, i=i: self._changer_vue(i))
        self.act_mois.setChecked(True)
        self.btn_vue.setMenu(self.menu_vue)
        b.addWidget(self.btn_vue)

        self.act_compact = bouton_icone("compact", "", 18, checkable=True)
        self.act_compact.toggled.connect(self._compact)
        self.btn_actualiser = bouton_icone("actualiser", "", 18)
        self.btn_actualiser.clicked.connect(lambda: self.synchroniser(forcer=True))
        self.btn_notifs = bouton_icone("cloche", "", 20)
        self.btn_notifs.clicked.connect(self._montrer_notifications)

        self.btn_plus = bouton_icone("plus_options", "", 20)
        self.btn_plus.setPopupMode(QToolButton.InstantPopup)
        self.menu_plus = QMenu(self)
        self.act_posts = self.menu_plus.addAction("", self._montrer_posts)
        self.act_perso = self.menu_plus.addAction("", self._liste_perso)
        self.menu_plus.addSeparator()
        self.act_compression = self.menu_plus.addAction("", self._compression)
        self.act_export = self.menu_plus.addAction("", self._export_pdf)
        self.btn_plus.setMenu(self.menu_plus)

        self.btn_langue = QToolButton()
        self.btn_langue.setPopupMode(QToolButton.InstantPopup)
        self.btn_langue.setFixedHeight(40)
        self.menu_langue = QMenu(self)
        for code, nom in textes.LANGUES.items():
            self.menu_langue.addAction(nom, lambda c=code: self._langue(c))
        self.btn_langue.setMenu(self.menu_langue)
        for w in (self.act_compact, self.btn_actualiser, self.btn_notifs, self.btn_plus, self.btn_langue):
            b.addWidget(w)

    def retraduire(self) -> None:
        self.setWindowTitle(t("app_titre"))
        self.nom_app.setText(t("app_nom"))
        self.btn_auj.setText(t("nav_aujourdhui"))
        self.btn_menu.setToolTip(t("masquer_menu"))
        self.btn_prec.setToolTip(t("nav_precedent"))
        self.btn_suiv.setToolTip(t("nav_suivant"))
        self.recherche.setPlaceholderText(t("recherche"))
        self.act_mois.setText(t("vue_mois"))
        self.act_semaine.setText(t("vue_semaine"))
        self.btn_vue.setToolTip(t("vue_choix"))
        self.act_compact.setToolTip(t("vue_compact_aide"))
        self.btn_actualiser.setToolTip(t("sync_bouton_actualiser"))
        self.btn_notifs.setToolTip(t("notifs"))
        self.btn_plus.setToolTip(t("menu_plus"))
        self.btn_langue.setText(textes.LANGUE.upper())
        self.btn_langue.setToolTip(t("langue"))
        self.act_posts.setText(t("post_liste_titre"))
        self.act_perso.setText(t("perso_gerer"))
        self.act_compression.setText(t("comp_menu"))
        self.act_export.setText(t("export_menu"))
        self.act_fab_perso.setText(t("fab_perso"))
        self.act_fab_post.setText(t("fab_post"))
        self.fab.setToolTip(t("fab_aide"))
        self.btn_fermer_panneau.setToolTip(t("panneau_fermer"))
        self.details.afficher(self.details.element)
        self.changements.remplir()
        self.aposter.remplir()
        self.liste_posts.remplir()
        self._badges()
        self._rafraichir_vues()

    # ------------------------------------------------------------------ navigation

    def vue_semaine_active(self) -> bool:
        return self.pile.currentIndex() == 1

    def _changer_vue(self, index: int) -> None:
        self.pile.setCurrentIndex(index)
        (self.act_semaine if index else self.act_mois).setChecked(True)
        self.act_compact.setEnabled(index == 0)
        self._rafraichir_vues()

    def _deplacer(self, sens: int) -> None:
        if self.vue_semaine_active():
            self.jour += timedelta(days=7 * sens)
        else:
            m = self.jour.month - 1 + sens
            self.jour = date(self.jour.year + m // 12, m % 12 + 1, 1)
        self._rafraichir_vues()

    def _aujourdhui(self) -> None:
        self.jour = date.today()
        self._rafraichir_vues()

    def _aller_semaine(self, jour: date) -> None:
        self.jour = jour
        self._changer_vue(1)

    def aller_a(self, jour: date, vue: int | None = None) -> None:
        self.jour = jour
        if vue is not None:
            self._changer_vue(vue)
        else:
            self._rafraichir_vues()

    def _rafraichir_vues(self) -> None:
        self.btn_vue.setText((t("vue_semaine") if self.vue_semaine_active() else t("vue_mois")) + "  ▾")
        if self.vue_semaine_active():
            self.vue_semaine.afficher_semaine(self.jour)
            lundi = self.vue_semaine.lundi
            dimanche = lundi + timedelta(days=6)
            if lundi.month == dimanche.month:
                titre = f"{nom_mois(lundi.month).capitalize()} {lundi.year}"
            else:
                titre = f"{nom_mois(lundi.month).capitalize()} – {nom_mois(dimanche.month)} {dimanche.year}"
            self.titre_periode.setText(titre)
            self.titre_periode.setToolTip(t("semaine_num", num=lundi.isocalendar()[1],
                                            debut=date_lisible(lundi), fin=date_lisible(dimanche, True)))
            debut, fin = lundi, dimanche
        else:
            self.vue_mois.afficher_mois(self.jour.year, self.jour.month)
            self.titre_periode.setText(f"{nom_mois(self.jour.month).capitalize()} {self.jour.year}")
            self.titre_periode.setToolTip("")
            debut, fin = self.vue_mois.lundis[0], self.vue_mois.lundis[-1] + timedelta(days=6)
        self.laterale.mini.montrer(self.jour)
        self.laterale.remplir(debut, fin)

    def _rechercher(self, texte: str) -> None:
        self.donnees.recherche = texte
        self._rafraichir_vues()

    def _compact(self, actif: bool) -> None:
        db.ecrire_reglage(self.conn, "mois_compact", "1" if actif else "0")
        self.vue_mois.basculer_compact(actif)
        self._barre_defilement_mois()
        self.act_compact.setIcon(style.icone("compact", th_mod.COULEUR_ACCENT if actif else CLAIR, 18))

    def _barre_defilement_mois(self) -> None:
        politique = Qt.ScrollBarAlwaysOff if self.vue_mois.compact else Qt.ScrollBarAsNeeded
        self.pile.widget(0).setVerticalScrollBarPolicy(politique)

    def _langue(self, code: str) -> None:
        textes.choisir_langue(code)
        db.ecrire_reglage(self.conn, "langue", code)
        self.retraduire()
        self._etat_sync_initial()

    # ------------------------------------------------------------------ panneau de droite

    def _ouvrir_panneau(self, onglet: QWidget) -> None:
        self.onglets.setCurrentWidget(onglet)
        self.titre_panneau.setText(self.onglets.tabText(self.onglets.currentIndex()))
        self.panneau.show()

    def _badges(self) -> None:
        n_chg = len(db.changements_depuis(self.conn, self.changements.vu_jusqua()))
        n_post = len(self.aposter.evenements)
        self.onglets.setTabText(0, t("details_titre"))
        self.onglets.setTabText(1, t("chg_compteur", n=n_chg) if n_chg else t("chg_titre"))
        self.onglets.setTabText(2, t("aposter_compteur", n=n_post) if n_post else t("aposter_titre"))
        self.onglets.setTabText(3, t("post_liste_titre"))
        self.btn_notifs.setIcon(style.icone("cloche", CLAIR, 20, badge=n_chg + n_post))
        self.btn_notifs.setToolTip(f"{t('notifs')} — {t('chg_compteur', n=n_chg)}, {t('aposter_compteur', n=n_post)}")
        if self.panneau.isVisible():
            self.titre_panneau.setText(self.onglets.tabText(self.onglets.currentIndex()))

    def _montrer_notifications(self) -> None:
        if self.panneau.isVisible() and self.onglets.currentWidget() in (self.changements, self.aposter):
            self.panneau.hide()
            return
        n_chg = len(db.changements_depuis(self.conn, self.changements.vu_jusqua()))
        self._ouvrir_panneau(self.changements if n_chg or not self.aposter.evenements else self.aposter)

    def _montrer_aposter(self) -> None:
        self._ouvrir_panneau(self.aposter)

    def _montrer_posts(self) -> None:
        self.liste_posts.remplir()
        self._ouvrir_panneau(self.liste_posts)

    def _element_clique(self, el: Element) -> None:
        self.vue_mois.selection = self.vue_semaine.selection = el.cle
        self.details.afficher(el)
        self._ouvrir_panneau(self.details)

    def _evenement_selectionne(self) -> dict | None:
        el = self.details.element
        return el.source if el and el.nature in ("event", "expo") and self.panneau.isVisible() else None

    def _evenement_choisi(self, uid: str) -> None:
        ligne = self.conn.execute("SELECT * FROM events WHERE uid=?", (uid,)).fetchone()
        if not ligne:
            return
        ev = db.ligne_vers_dict(ligne)
        debut = datetime.fromisoformat(ev["start"])
        cible = max(debut.date(), date.today()) if ev["type"] == "exposition" else debut.date()
        onglet = self.onglets.currentWidget()
        self.aller_a(cible)
        for el in (self.vue_semaine if self.vue_semaine_active() else self.vue_mois).elements:
            if el.cle == f"ev:{uid}":
                self.vue_mois.selection = self.vue_semaine.selection = el.cle
                self.details.afficher(el)
                self.vue_mois.update()
                self.vue_semaine.update()
                break
        self._ouvrir_panneau(onglet)  # on reste sur la liste ; le détail est prêt dans l'onglet 1

    # ------------------------------------------------------------------ posts

    def nouveau_post(self, evenement: dict | None = None) -> None:
        precoches = [evenement["uid"]] if evenement else []
        if DialoguePost(self.conn, self, precoches=precoches).exec():
            self._posts_modifies()

    def modifier_post(self, id_: int) -> None:
        post = db.lire_post(self.conn, id_)
        if post and DialoguePost(self.conn, self, post=post).exec():
            self._posts_modifies()

    def _posts_modifies(self) -> None:
        self.aposter.remplir()
        self.liste_posts.remplir()
        self._badges()
        self._rafraichir_vues()
        el = self.details.element
        if el and el.nature == "post" and not db.lire_post(self.conn, el.source["id"]):
            self.details.afficher(None)
        else:
            self.details.rafraichir()

    # ------------------------------------------------------------------ vie de Zoune

    def _nouveau_perso(self, debut: datetime, journee: bool) -> None:
        if DialoguePerso(self.conn, self, debut=debut, journee=journee).exec():
            self._rafraichir_vues()

    def _modifier_perso(self, id_: int) -> None:
        element = db.lire_perso(self.conn, id_)
        if element and DialoguePerso(self.conn, self, element=element).exec():
            self.details.afficher(None)
            self._rafraichir_vues()

    def _liste_perso(self) -> None:
        dialogue = ListePerso(self.conn, self)
        dialogue.exec()
        if dialogue.modifie:
            self.details.afficher(None)
            self._rafraichir_vues()

    # ------------------------------------------------------------------ outils

    def _compression(self) -> None:
        from .outils import DialogueCompression
        DialogueCompression(self).exec()

    def _export_pdf(self) -> None:
        from .outils import DialogueExport
        DialogueExport(self).exec()

    # ------------------------------------------------------------------ notifications

    def _icone_notification(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        icone = QSystemTrayIcon(QIcon(logo(32)), self)
        icone.setToolTip("Musée Zoune")
        icone.activated.connect(lambda _r: (self.showNormal(), self.activateWindow(), self._montrer_aposter()))
        icone.messageClicked.connect(lambda: (self.showNormal(), self.activateWindow(), self._montrer_aposter()))
        icone.show()
        return icone

    def notifier_a_poster(self) -> None:
        """Notification Windows discrète, une seule fois par jour, s'il reste des posts à faire."""
        aujourdhui = date.today()
        n = len(self.aposter.evenements)
        if n == 0 or not notification_a_faire(self.conn, aujourdhui):
            return
        if self.icone_notif is not None:
            self.icone_notif.showMessage(t("aposter_notif_titre"), t("aposter_notif", n=n),
                                         QSystemTrayIcon.Information, 8000)
        noter_notification(self.conn, aujourdhui)

    # ------------------------------------------------------------------ synchronisation

    def _etat_sync_initial(self) -> None:
        derniere = derniere_sync(self.conn)
        if derniere:
            self.laterale.set_statut(t("statut_sync_rien", heure=derniere.strftime("%d/%m %H:%M")))

    def synchroniser(self, forcer: bool) -> None:
        if self.fil and self.fil.isRunning():
            return
        self.btn_actualiser.setEnabled(False)
        self.laterale.set_statut(t("statut_sync_en_cours"))
        self.fil = FilSync(forcer, self)
        self.fil.termine.connect(self._sync_terminee)
        self.fil.echec.connect(self._sync_echec)
        self.fil.finished.connect(lambda: self.btn_actualiser.setEnabled(True))
        self.fil.start()

    def _sync_terminee(self, resume) -> None:
        self.donnees.recharger()
        self.changements.remplir()
        self.aposter.remplir()
        self._badges()
        self._rafraichir_vues()
        if resume is None:
            self._etat_sync_initial()
        else:
            self.laterale.set_statut(t("statut_sync_ok", heure=datetime.now().strftime("%H:%M")))
        self.notifier_a_poster()

    def _sync_echec(self, _erreur: str) -> None:
        derniere = derniere_sync(self.conn)
        self.laterale.set_statut(
            t("statut_hors_ligne", date=derniere.strftime("%d/%m/%Y %H:%M")) if derniere
            else t("statut_jamais_sync"), alerte=True)
        self.notifier_a_poster()  # hors ligne : rappel avec les données en base

    # ------------------------------------------------------------------ Qt

    def eventFilter(self, objet, ev):
        if objet is getattr(self, "cadre_vue", None) and ev.type() == ev.Type.Resize:
            self.fab.move(objet.width() - self.fab.width() - 36, objet.height() - self.fab.height() - 24)
            self.fab.raise_()
        return super().eventFilter(objet, ev)

    def closeEvent(self, ev):
        if self.fil and self.fil.isRunning():
            self.fil.wait(15000)
        super().closeEvent(ev)
