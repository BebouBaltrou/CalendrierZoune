"""Fenêtre principale de Musée Zoune."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDockWidget, QLabel, QMainWindow, QPushButton, QScrollArea, QSizePolicy,
    QMenu, QStackedWidget, QSystemTrayIcon, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from .. import db, textes
from ..sync import derniere_sync, lancer_sync, sync_necessaire
from ..textes import date_lisible, nom_mois, t
from .dialogues import DialoguePerso, ListePerso
from .donnees import Donnees, Element, noter_notification, notification_a_faire
from .panneaux import APoster, Changements, Details, Legende
from .vue_mois import VueMois
from .vue_semaine import VueSemaine

log = logging.getLogger("musee_zoune.app")


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


class FenetrePrincipale(QMainWindow):
    def __init__(self, conn, synchroniser_au_demarrage: bool = True):
        super().__init__()
        self.conn = conn
        textes.choisir_langue(db.lire_reglage(conn, "langue", "fr"))
        self.donnees = Donnees(conn)
        self.jour = date.today()
        self.fil: FilSync | None = None
        self.resize(1400, 860)

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

        # bandeau des changements non lus
        self.bandeau = QPushButton()
        self.bandeau.setCursor(Qt.PointingHandCursor)
        self.bandeau.setStyleSheet(
            "QPushButton { background:#FFF4D6; border:none; border-bottom:1px solid #E8D9A8;"
            " padding:6px; text-align:left; font-weight:bold; color:#6B4E00; }")
        self.bandeau.clicked.connect(self._montrer_changements)
        self.bandeau_aposter = QPushButton()
        self.bandeau_aposter.setCursor(Qt.PointingHandCursor)
        self.bandeau_aposter.setStyleSheet(
            "QPushButton { background:#FFE8D6; border:none; border-bottom:1px solid #F2B98F;"
            " padding:6px; text-align:left; font-weight:bold; color:#8A3B00; }")
        self.bandeau_aposter.clicked.connect(self._montrer_aposter)
        self.titre_periode = QLabel()
        self.titre_periode.setStyleSheet("font-size:18px; font-weight:bold; padding:6px 8px;")
        centre = QWidget()
        layout = QVBoxLayout(centre)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.bandeau)
        layout.addWidget(self.bandeau_aposter)
        layout.addWidget(self.titre_periode)
        layout.addWidget(self.pile)
        self.setCentralWidget(centre)

        # panneaux
        self.legende = Legende(self.donnees)
        self.details = Details(self.donnees)
        self.changements = Changements(conn)
        self.aposter = APoster(conn)
        self.dock_legende = self._dock(self.legende, Qt.LeftDockWidgetArea)
        self.dock_details = self._dock(self.details, Qt.RightDockWidgetArea)
        self.dock_chg = self._dock(self.changements, Qt.RightDockWidgetArea)
        self.dock_aposter = self._dock(self.aposter, Qt.RightDockWidgetArea)
        self.tabifyDockWidget(self.dock_details, self.dock_chg)
        self.tabifyDockWidget(self.dock_chg, self.dock_aposter)
        self.dock_legende.setMinimumWidth(260)
        self.dock_details.setMinimumWidth(330)

        self._barre_outils()
        self.message_statut = QLabel()
        self.statusBar().addWidget(self.message_statut, 1)

        # signaux
        for vue in (self.vue_mois, self.vue_semaine):
            vue.element_clique.connect(self._element_clique)
        self.vue_mois.jour_double_clique.connect(lambda j: self._nouveau_perso(datetime.combine(j, datetime.min.time()), True))
        self.vue_mois.jour_choisi.connect(self._aller_semaine)
        self.vue_semaine.creneau_double_clique.connect(lambda m: self._nouveau_perso(m, False))
        self.legende.filtre_change.connect(self._rafraichir_vues)
        self.legende.expo_choisie.connect(self._evenement_choisi)
        self.details.modifier_perso.connect(self._modifier_perso)
        self.changements.evenement_choisi.connect(self._evenement_choisi)
        self.changements.compteur_change.connect(self._compteur)
        self.details.posts_modifies.connect(self._posts_modifies)
        self.aposter.evenement_choisi.connect(self._evenement_choisi)
        self.aposter.compteur_change.connect(self._compteur_aposter)
        self.icone_notif = self._icone_notification()

        self._barre_defilement_mois()
        self.retraduire()
        self.dock_chg.raise_() if self._non_lus() else self.dock_details.raise_()
        self._etat_sync_initial()
        self.aposter.remplir()
        if synchroniser_au_demarrage and sync_necessaire(conn):
            self.synchroniser(forcer=False)  # le rappel sera notifié après la synchro
        elif synchroniser_au_demarrage:
            self.notifier_a_poster()

    # ------------------------------------------------------------------ construction

    def _dock(self, widget, zone) -> QDockWidget:
        dock = QDockWidget(self)
        dock.setWidget(widget)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(zone, dock)
        return dock

    def _barre_outils(self) -> None:
        barre = QToolBar()
        barre.setMovable(False)
        barre.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(barre)
        self.act_prec = barre.addAction("", lambda: self._deplacer(-1))
        self.act_auj = barre.addAction("", self._aujourdhui)
        self.act_suiv = barre.addAction("", lambda: self._deplacer(1))
        barre.addSeparator()
        groupe = QActionGroup(self)
        self.act_mois = QAction(self, checkable=True)
        self.act_semaine = QAction(self, checkable=True)
        for i, act in enumerate((self.act_mois, self.act_semaine)):
            groupe.addAction(act)
            barre.addAction(act)
            act.triggered.connect(lambda _=False, i=i: self._changer_vue(i))
        self.act_mois.setChecked(True)
        self.act_compact = QAction(self, checkable=True)
        self.act_compact.setChecked(db.lire_reglage(self.conn, "mois_compact", "0") == "1")
        self.vue_mois.compact = self.act_compact.isChecked()
        self.act_compact.toggled.connect(self._compact)
        barre.addAction(self.act_compact)
        barre.addSeparator()
        self.lbl_ville = QLabel()
        self.combo_ville = QComboBox()
        self.combo_ville.currentIndexChanged.connect(self._ville)
        barre.addWidget(self.lbl_ville)
        barre.addWidget(self.combo_ville)
        barre.addSeparator()
        self.act_sans_post = QAction(self, checkable=True)
        self.act_sans_post.toggled.connect(self._filtre_sans_post)
        barre.addAction(self.act_sans_post)
        barre.addSeparator()
        self.act_perso = barre.addAction("", self._liste_perso)
        self.menu_outils = QMenu(self)
        self.act_compression = self.menu_outils.addAction("", self._compression)
        self.act_export = self.menu_outils.addAction("", self._export_pdf)
        self.btn_outils = QToolButton()
        self.btn_outils.setMenu(self.menu_outils)
        self.btn_outils.setPopupMode(QToolButton.InstantPopup)
        barre.addWidget(self.btn_outils)
        espace = QWidget()
        espace.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        barre.addWidget(espace)
        self.act_actualiser = barre.addAction("", lambda: self.synchroniser(forcer=True))
        barre.addSeparator()
        self.lbl_langue = QLabel()
        self.combo_langue = QComboBox()
        for code, nom in textes.LANGUES.items():
            self.combo_langue.addItem(nom, code)
        self.combo_langue.setCurrentIndex(self.combo_langue.findData(textes.LANGUE))
        self.combo_langue.currentIndexChanged.connect(self._langue)
        barre.addWidget(self.lbl_langue)
        barre.addWidget(self.combo_langue)

    def retraduire(self) -> None:
        self.setWindowTitle(t("app_titre"))
        self.act_prec.setText(t("nav_precedent"))
        self.act_suiv.setText(t("nav_suivant"))
        self.act_auj.setText(t("nav_aujourdhui"))
        self.act_mois.setText(t("vue_mois"))
        self.act_semaine.setText(t("vue_semaine"))
        self.act_compact.setText(t("vue_compact"))
        self.act_compact.setToolTip(t("vue_compact_aide"))
        self.act_perso.setText(t("perso_gerer"))
        self.btn_outils.setText(t("outils") + " ▾")
        self.act_compression.setText(t("comp_menu"))
        self.act_export.setText(t("export_menu"))
        self.act_sans_post.setText("● " + t("filtre_sans_post"))
        self.act_sans_post.setToolTip(t("filtre_sans_post_aide"))
        self.act_actualiser.setText("⟳ " + t("sync_bouton_actualiser"))
        self.lbl_ville.setText(t("filtre_ville") + " ")
        self.lbl_langue.setText(t("langue") + " ")
        self.dock_legende.setWindowTitle(t("legende_titre"))
        self.dock_details.setWindowTitle(t("details_titre"))
        self._remplir_villes()
        self.details.afficher(self.details.element)
        self.changements.remplir()
        if hasattr(self, "aposter"):
            self.aposter.remplir()
        self._rafraichir_vues()

    def _remplir_villes(self) -> None:
        actuelle = self.donnees.ville
        self.combo_ville.blockSignals(True)
        self.combo_ville.clear()
        self.combo_ville.addItem(t("filtre_toutes_villes"), None)
        for ville in self.donnees.villes():
            self.combo_ville.addItem(ville, ville)
        self.combo_ville.setCurrentIndex(max(0, self.combo_ville.findData(actuelle)))
        self.combo_ville.blockSignals(False)

    # ------------------------------------------------------------------ navigation

    def vue_semaine_active(self) -> bool:
        return self.pile.currentIndex() == 1

    def _changer_vue(self, index: int) -> None:
        self.pile.setCurrentIndex(index)
        (self.act_semaine if index else self.act_mois).setChecked(True)
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
        if self.vue_semaine_active():
            self.vue_semaine.afficher_semaine(self.jour)
            lundi = self.vue_semaine.lundi
            dimanche = lundi + timedelta(days=6)
            self.titre_periode.setText(t("semaine_num", num=lundi.isocalendar()[1],
                                         debut=date_lisible(lundi), fin=date_lisible(dimanche, True)))
            self.legende.remplir(lundi, dimanche)
        else:
            self.vue_mois.afficher_mois(self.jour.year, self.jour.month)
            self.titre_periode.setText(f"{nom_mois(self.jour.month).capitalize()} {self.jour.year}")
            self.legende.remplir(self.vue_mois.lundis[0], self.vue_mois.lundis[-1] + timedelta(days=6))

    def _barre_defilement_mois(self) -> None:
        politique = Qt.ScrollBarAlwaysOff if self.vue_mois.compact else Qt.ScrollBarAsNeeded
        self.pile.widget(0).setVerticalScrollBarPolicy(politique)

    def _compact(self, actif: bool) -> None:
        db.ecrire_reglage(self.conn, "mois_compact", "1" if actif else "0")
        self.vue_mois.basculer_compact(actif)
        self._barre_defilement_mois()
        if self.vue_semaine_active():
            self._changer_vue(0)

    def _compression(self) -> None:
        from .outils import DialogueCompression
        DialogueCompression(self).exec()

    def _export_pdf(self) -> None:
        from .outils import DialogueExport
        DialogueExport(self).exec()

    def _filtre_sans_post(self, actif: bool) -> None:
        self.donnees.sans_post_seulement = actif
        self._rafraichir_vues()

    def _ville(self) -> None:
        self.donnees.ville = self.combo_ville.currentData()
        self._rafraichir_vues()

    def _langue(self) -> None:
        code = self.combo_langue.currentData()
        textes.choisir_langue(code)
        db.ecrire_reglage(self.conn, "langue", code)
        self.retraduire()
        self._etat_sync_initial()

    # ------------------------------------------------------------------ sélection

    def _element_clique(self, el: Element) -> None:
        self.vue_mois.selection = self.vue_semaine.selection = el.cle
        self.details.afficher(el)
        self.dock_details.raise_()

    def _evenement_choisi(self, uid: str) -> None:
        ligne = self.conn.execute("SELECT * FROM events WHERE uid=?", (uid,)).fetchone()
        if not ligne:
            return
        ev = db.ligne_vers_dict(ligne)
        debut = datetime.fromisoformat(ev["start"])
        cible = max(debut.date(), date.today()) if ev["type"] == "exposition" else debut.date()
        self.aller_a(cible)
        for el in (self.vue_semaine if self.vue_semaine_active() else self.vue_mois).elements:
            if el.cle == f"ev:{uid}":
                self._element_clique(el)
                self.vue_mois.update()
                self.vue_semaine.update()
                return

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

    # ------------------------------------------------------------------ changements

    def _non_lus(self) -> int:
        return len(db.changements_depuis(self.conn, self.changements.vu_jusqua()))

    def _compteur(self, n: int) -> None:
        self.dock_chg.setWindowTitle(t("chg_compteur", n=n) if n else t("chg_titre"))
        self.bandeau.setVisible(n > 0)
        self.bandeau.setText(f"● {t('chg_bandeau', n=n)}")

    def _compteur_aposter(self, n: int) -> None:
        self.dock_aposter.setWindowTitle(t("aposter_compteur", n=n) if n else t("aposter_titre"))
        self.bandeau_aposter.setVisible(n > 0)
        self.bandeau_aposter.setText(f"● {t('aposter_bandeau', n=n)}")

    def _montrer_aposter(self) -> None:
        self.dock_aposter.show()
        self.dock_aposter.raise_()

    def _posts_modifies(self) -> None:
        self.aposter.remplir()
        self.vue_mois.recalculer() if not self.vue_semaine_active() else self.vue_semaine.recalculer()
        self._rafraichir_vues()

    def _icone_notification(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#7E57C2"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(2, 2, 28, 28, 7, 7)
        p.setPen(QColor("white"))
        f = p.font()
        f.setBold(True)
        f.setPointSize(15)
        p.setFont(f)
        p.drawText(pix.rect(), Qt.AlignCenter, "Z")
        p.end()
        icone = QSystemTrayIcon(QIcon(pix), self)
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

    def _montrer_changements(self) -> None:
        self.dock_chg.show()
        self.dock_chg.raise_()

    # ------------------------------------------------------------------ synchronisation

    def _etat_sync_initial(self) -> None:
        derniere = derniere_sync(self.conn)
        if derniere:
            self.message_statut.setText(t("statut_sync_rien", heure=derniere.strftime("%d/%m %H:%M")))

    def synchroniser(self, forcer: bool) -> None:
        if self.fil and self.fil.isRunning():
            return
        self.act_actualiser.setEnabled(False)
        self.message_statut.setText(t("statut_sync_en_cours"))
        self.fil = FilSync(forcer, self)
        self.fil.termine.connect(self._sync_terminee)
        self.fil.echec.connect(self._sync_echec)
        self.fil.finished.connect(lambda: self.act_actualiser.setEnabled(True))
        self.fil.start()

    def _sync_terminee(self, resume) -> None:
        self.donnees.recharger()
        self._remplir_villes()
        self.changements.remplir()
        self.aposter.remplir()
        self._rafraichir_vues()
        self.notifier_a_poster()
        self.message_statut.setStyleSheet("")
        if resume is None:
            self._etat_sync_initial()
        else:
            self.message_statut.setText(t("statut_sync_ok", heure=datetime.now().strftime("%H:%M")))

    def _sync_echec(self, _erreur: str) -> None:
        self.notifier_a_poster()  # hors ligne : rappel avec les données en base
        derniere = derniere_sync(self.conn)
        self.message_statut.setText(
            t("statut_hors_ligne", date=derniere.strftime("%d/%m/%Y %H:%M")) if derniere
            else t("statut_jamais_sync"))
        self.message_statut.setStyleSheet("color:#8A5A00;")

    def closeEvent(self, ev):
        if self.fil and self.fil.isRunning():
            self.fil.wait(15000)
        super().closeEvent(ev)
