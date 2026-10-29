"""Fenêtre « Paramètres » (menu ⋯) et mises à jour de l'application."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QRadioButton, QTextBrowser, QVBoxLayout,
)

from .. import config, db, maj
from ..textes import t

log = logging.getLogger("musee_zoune.app")
REGLAGE_MODE = "maj_mode"                 # "auto" ou "manuel"
REGLAGE_DERNIERE = "maj_derniere_verif"   # date ISO de la dernière vérification réussie


class FilMaj(QThread):
    """Vérification ou préparation d'une mise à jour, en arrière-plan."""

    verifiee = Signal(object)   # maj.Release
    preparee = Signal(object)   # Path du dossier d'attente
    echec = Signal(str)

    def __init__(self, release: maj.Release | None = None, choix: maj.Choix | None = None):
        super().__init__()
        self.release, self.choix = release, choix

    def run(self):
        try:
            if self.choix is None:
                self.verifiee.emit(maj.verifier())
            else:
                self.preparee.emit(maj.preparer(self.release, self.choix, maj.dossier_application(),
                                                arreter=self.isInterruptionRequested))
        except Exception as exc:  # noqa: BLE001 — pas d'internet, GitHub indisponible…
            log.info("mise à jour : %s", exc)
            self.echec.emit(str(exc))


class GestionMaj(QObject):
    """Vérifie, télécharge et fait installer les mises à jour (auto au lancement ou manuel)."""

    etat_change = Signal()

    def __init__(self, fenetre, conn):
        super().__init__(fenetre)
        self.fenetre, self.conn = fenetre, conn
        self.fil: FilMaj | None = None
        self.message = ""

    # réglages
    def mode(self) -> str:
        return "manuel" if db.lire_reglage(self.conn, REGLAGE_MODE, "auto") == "manuel" else "auto"

    def choisir_mode(self, mode: str) -> None:
        db.ecrire_reglage(self.conn, REGLAGE_MODE, mode)

    def derniere_verification(self) -> datetime | None:
        valeur = db.lire_reglage(self.conn, REGLAGE_DERNIERE)
        try:
            return datetime.fromisoformat(valeur) if valeur else None
        except ValueError:
            return None

    def occupe(self) -> bool:
        return self.fil is not None and self.fil.isRunning()

    # déroulement
    def demarrage(self) -> None:
        if self.mode() == "auto":
            QTimer.singleShot(4000, lambda: self.verifier(silencieux=True))

    def verifier(self, silencieux: bool) -> None:
        if self.occupe():
            return
        self._etat(t("maj_en_cours"))
        self.fil = FilMaj()
        self.fil.verifiee.connect(lambda r: self._verifiee(r, silencieux))
        self.fil.echec.connect(lambda e: self._echec_verif(e, silencieux))
        self.fil.finished.connect(self.etat_change.emit)
        self.fil.start()

    def _verifiee(self, release: maj.Release, silencieux: bool) -> None:
        db.ecrire_reglage(self.conn, REGLAGE_DERNIERE, datetime.now().isoformat(timespec="seconds"))
        self._etat("")
        if not maj.plus_recente(release.version, config.VERSION):
            if not silencieux:
                QMessageBox.information(self._parent(), t("maj_section"),
                                        t("maj_a_jour", version=config.VERSION))
            return
        choix = maj.choisir_paquet(release, config.VERSION)
        if silencieux:  # mode automatique : installer sans rien demander, sauf le redémarrage
            if choix is not None and config.est_installee():
                self.installer(release, choix, silencieux=True)
            return
        self._proposer(release, choix)

    def _echec_verif(self, erreur: str, silencieux: bool) -> None:
        self._etat("")
        if not silencieux:
            QMessageBox.warning(self._parent(), t("maj_section"), t("maj_erreur_verif", erreur=erreur))

    def _proposer(self, release: maj.Release, choix: maj.Choix | None) -> None:
        dlg = QDialog(self._parent())
        dlg.setWindowTitle(t("maj_disponible_titre"))
        dlg.resize(560, 460)
        lay = QVBoxLayout(dlg)
        titre = QLabel(t("maj_disponible", version=release.version, actuelle=config.VERSION))
        titre.setWordWrap(True)
        lay.addWidget(titre)
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setMarkdown(release.notes_affichables())
        lay.addWidget(notes, 1)
        boutons = QDialogButtonBox()
        if not config.est_installee():
            info = t("maj_dev")
        elif choix is None:
            info = t("maj_sans_paquet")
        else:
            info = t("maj_complete", taille=f"{choix.archive.taille / 1048576:.0f}") if choix.mode == "dossier" else ""
            boutons.addButton(t("maj_installer"), QDialogButtonBox.AcceptRole)
        if info:
            etiquette = QLabel(info)
            etiquette.setWordWrap(True)
            lay.addWidget(etiquette)
        if release.page:
            page = boutons.addButton(t("maj_voir_page"), QDialogButtonBox.ActionRole)
            page.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(release.page)))
        boutons.addButton(t("maj_plus_tard"), QDialogButtonBox.RejectRole)
        boutons.accepted.connect(dlg.accept)
        boutons.rejected.connect(dlg.reject)
        lay.addWidget(boutons)
        if dlg.exec() == QDialog.Accepted and choix is not None:
            self.installer(release, choix, silencieux=False)

    def installer(self, release: maj.Release, choix: maj.Choix, silencieux: bool) -> None:
        if self.fil is not None and self.fil.choix is None:
            self.fil.wait(3000)  # le fil de vérification se termine juste après son signal
        if self.occupe() or not config.est_installee():
            return
        self._etat(t("maj_telechargement", version=release.version))
        self.fil = FilMaj(release, choix)
        self.fil.preparee.connect(lambda attente: self._preparee(release, attente))
        self.fil.echec.connect(lambda e: self._echec_install(e, silencieux))
        self.fil.finished.connect(self.etat_change.emit)
        self.fil.start()

    def _echec_install(self, erreur: str, silencieux: bool) -> None:
        self._etat("")
        if not silencieux:
            QMessageBox.warning(self._parent(), t("maj_section"), t("maj_erreur_install", erreur=erreur))

    def _preparee(self, release: maj.Release, attente) -> None:
        self._etat("")
        boite = QMessageBox(self._parent())
        boite.setIcon(QMessageBox.Information)
        boite.setWindowTitle(t("maj_prete_titre"))
        boite.setText(t("maj_prete", version=release.version))
        maintenant = boite.addButton(t("maj_redemarrer"), QMessageBox.AcceptRole)
        boite.addButton(t("maj_plus_tard"), QMessageBox.RejectRole)
        boite.exec()
        relancer = boite.clickedButton() is maintenant
        try:
            # dans les deux cas le script attend la fermeture ; « Plus tard » : sans relance
            maj.lancer_application(attente, maj.dossier_application(), os.getpid(), relancer)
        except Exception as exc:  # noqa: BLE001
            log.warning("script de mise à jour non lancé : %s", exc)
            QMessageBox.warning(self._parent(), t("maj_section"), t("maj_erreur_install", erreur=exc))
            return
        if relancer:
            self.fenetre.close()
            QApplication.quit()

    def arreter(self) -> None:
        if self.occupe():
            self.fil.requestInterruption()
            self.fil.wait(5000)

    def _etat(self, message: str) -> None:
        self.message = message
        self.etat_change.emit()

    def _parent(self):
        return QApplication.activeModalWidget() or self.fenetre


class DialogueParametres(QDialog):
    def __init__(self, gestion: GestionMaj, parent=None):
        super().__init__(parent)
        self.gestion = gestion
        self.setWindowTitle(t("param_titre"))
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)

        groupe = QGroupBox(t("maj_section"))
        g = QVBoxLayout(groupe)
        self.radio_auto = QRadioButton(t("maj_auto"))
        self.radio_manuel = QRadioButton(t("maj_manuel"))
        self.choix_mode = QButtonGroup(self)
        for r in (self.radio_auto, self.radio_manuel):
            self.choix_mode.addButton(r)
            g.addWidget(r)
        (self.radio_manuel if gestion.mode() == "manuel" else self.radio_auto).setChecked(True)
        self.radio_auto.toggled.connect(
            lambda actif: gestion.choisir_mode("auto" if actif else "manuel"))
        self.lbl_version = QLabel(t("maj_version_actuelle", version=config.VERSION))
        self.lbl_derniere = QLabel()
        self.lbl_etat = QLabel()
        self.lbl_etat.setWordWrap(True)
        for w in (self.lbl_version, self.lbl_derniere):
            g.addWidget(w)
        if not config.est_installee():
            dev = QLabel(t("maj_dev"))
            dev.setWordWrap(True)
            g.addWidget(dev)
        ligne = QHBoxLayout()
        self.btn_rechercher = QPushButton(t("maj_rechercher"))
        self.btn_rechercher.clicked.connect(lambda: gestion.verifier(silencieux=False))
        ligne.addWidget(self.btn_rechercher)
        ligne.addStretch(1)
        g.addLayout(ligne)
        g.addWidget(self.lbl_etat)
        lay.addWidget(groupe)

        boutons = QDialogButtonBox()
        boutons.addButton(t("bouton_fermer"), QDialogButtonBox.RejectRole)
        boutons.rejected.connect(self.reject)
        lay.addWidget(boutons)
        gestion.etat_change.connect(self.rafraichir)
        self.rafraichir()

    def rafraichir(self) -> None:
        derniere = self.gestion.derniere_verification()
        self.lbl_derniere.setText(t("maj_derniere_verif",
                                    date=derniere.strftime("%d/%m/%Y %H:%M") if derniere else t("maj_jamais")))
        self.lbl_etat.setText(self.gestion.message)
        self.lbl_etat.setVisible(bool(self.gestion.message))
        self.btn_rechercher.setEnabled(not self.gestion.occupe())

    def done(self, r):
        try:
            self.gestion.etat_change.disconnect(self.rafraichir)
        except (RuntimeError, TypeError):
            pass
        super().done(r)
