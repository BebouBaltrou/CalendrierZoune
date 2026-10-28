"""Menu « Outils » : compression de fichiers et export PDF du calendrier."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from .. import compression as cp
from ..textes import t


def ko(octets: int) -> str:
    return f"{octets / 1024:,.0f} Ko".replace(",", " ")


class FilCompression(QThread):
    resultat = Signal(int, object)  # ligne, cp.Resultat

    def __init__(self, fichiers: list[tuple[int, Path]], reglage: cp.Reglage, parent=None):
        super().__init__(parent)
        self.fichiers, self.reglage = fichiers, reglage

    def run(self):
        for ligne, chemin in self.fichiers:
            self.resultat.emit(ligne, cp.compresser(chemin, self.reglage))


class TableFichiers(QTableWidget):
    """Tableau qui accepte le glisser-déposer de fichiers."""

    fichiers_deposes = Signal(list)

    def __init__(self, parent=None):
        super().__init__(0, 5, parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 5):
            self.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        chemins = [Path(u.toLocalFile()) for u in ev.mimeData().urls() if u.isLocalFile()]
        self.fichiers_deposes.emit(chemins)
        ev.acceptProposedAction()


class DialogueCompression(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("comp_titre"))
        self.resize(820, 480)
        self.fichiers: list[Path] = []
        self.fil: FilCompression | None = None

        aide = QLabel(t("comp_aide"))
        aide.setWordWrap(True)
        self.table = TableFichiers()
        self.table.setHorizontalHeaderLabels(
            [t("comp_col_fichier"), t("comp_col_avant"), t("comp_col_apres"), t("comp_col_gain"),
             t("comp_col_resultat")])
        self.table.fichiers_deposes.connect(self.ajouter)
        self.table.cellDoubleClicked.connect(self._ouvrir_dossier)

        self.prereglage = QComboBox()
        for code in ("mail", "web", "impression", "perso"):
            self.prereglage.addItem(t("comp_pre_" + code), code)
        self.max_px = QSpinBox()
        self.max_px.setRange(200, 10000)
        self.max_px.setSingleStep(100)
        self.max_px.setSuffix(" px")
        self.qualite = QSpinBox()
        self.qualite.setRange(10, 95)
        self.prereglage.currentIndexChanged.connect(self._prereglage)
        self._prereglage()

        reglages = QHBoxLayout()
        reglages.addWidget(QLabel(t("comp_prereglage")))
        reglages.addWidget(self.prereglage)
        reglages.addSpacing(16)
        reglages.addWidget(QLabel(t("comp_max_px")))
        reglages.addWidget(self.max_px)
        reglages.addWidget(QLabel(t("comp_qualite")))
        reglages.addWidget(self.qualite)
        reglages.addStretch()

        choisir = QPushButton(t("comp_choisir"))
        choisir.clicked.connect(self._choisir)
        vider = QPushButton(t("comp_vider"))
        vider.clicked.connect(self._vider)
        self.lancer = QPushButton(t("comp_lancer"))
        self.lancer.setDefault(True)
        self.lancer.clicked.connect(self._lancer)
        fermer = QPushButton(t("bouton_fermer"))
        fermer.clicked.connect(self.accept)
        boutons = QHBoxLayout()
        for b in (choisir, vider):
            boutons.addWidget(b)
        boutons.addStretch()
        boutons.addWidget(self.lancer)
        boutons.addWidget(fermer)

        self.resume = QLabel()
        layout = QVBoxLayout(self)
        layout.addWidget(aide)
        layout.addLayout(reglages)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.resume)
        layout.addLayout(boutons)

    def _reglage(self) -> cp.Reglage:
        code = self.prereglage.currentData()
        if code == "perso":
            return cp.reglage_perso(self.max_px.value(), self.qualite.value())
        return cp.PREREGLAGES[code]

    def _prereglage(self) -> None:
        code = self.prereglage.currentData()
        perso = code == "perso"
        if not perso:
            r = cp.PREREGLAGES[code]
            self.max_px.setValue(r.max_px)
            self.qualite.setValue(r.qualite)
        self.max_px.setEnabled(perso)
        self.qualite.setEnabled(perso)

    def _choisir(self) -> None:
        filtre = t("comp_filtre") + " (*.jpg *.jpeg *.png *.heic *.heif *.webp *.tif *.tiff *.pdf)"
        chemins, _ = QFileDialog.getOpenFileNames(self, t("comp_choisir"), str(Path.home()), filtre)
        self.ajouter([Path(c) for c in chemins])

    def ajouter(self, chemins: list[Path]) -> None:
        for chemin in chemins:
            if chemin.is_dir() or chemin in self.fichiers:
                continue
            ligne = self.table.rowCount()
            self.table.insertRow(ligne)
            self.fichiers.append(chemin)
            nom = QTableWidgetItem(chemin.name)
            nom.setToolTip(str(chemin))
            self.table.setItem(ligne, 0, nom)
            self.table.setItem(ligne, 1, QTableWidgetItem(ko(chemin.stat().st_size)))
            etat = "" if cp.est_pris_en_charge(chemin) else t("comp_non_pris_en_charge")
            for col, texte in ((2, ""), (3, ""), (4, etat)):
                self.table.setItem(ligne, col, QTableWidgetItem(texte))

    def _vider(self) -> None:
        if self.fil and self.fil.isRunning():
            return
        self.table.setRowCount(0)
        self.fichiers = []
        self.resume.clear()

    def _lancer(self) -> None:
        a_faire = [(i, c) for i, c in enumerate(self.fichiers)
                   if cp.est_pris_en_charge(c) and not self.table.item(i, 2).text()]
        if not a_faire or (self.fil and self.fil.isRunning()):
            return
        for i, _ in a_faire:
            self.table.item(i, 4).setText(t("comp_en_cours"))
        self.lancer.setEnabled(False)
        self.fil = FilCompression(a_faire, self._reglage(), self)
        self.fil.resultat.connect(self._resultat)
        self.fil.finished.connect(self._fini)
        self.fil.start()

    def _resultat(self, ligne: int, r: cp.Resultat) -> None:
        if r.ok:
            self.table.item(ligne, 2).setText(ko(r.apres))
            self.table.item(ligne, 3).setText(f"{r.gain:+.0%}".replace("+", "−") if r.gain > 0
                                              else f"+{-r.gain:.0%}")
            self.table.item(ligne, 4).setText(r.sortie.name)
            self.table.item(ligne, 4).setToolTip(str(r.sortie))
            self.table.item(ligne, 4).setData(Qt.UserRole, str(r.sortie))
        else:
            self.table.item(ligne, 4).setText(t("comp_erreur", erreur=r.message))

    def _fini(self) -> None:
        self.lancer.setEnabled(True)
        avant = apres = 0
        for i in range(self.table.rowCount()):
            if self.table.item(i, 4).data(Qt.UserRole):
                avant += self.fichiers[i].stat().st_size
                apres += Path(self.table.item(i, 4).data(Qt.UserRole)).stat().st_size
        if avant:
            self.resume.setText(t("comp_resume", avant=ko(avant), apres=ko(apres)))

    def _ouvrir_dossier(self, ligne: int, _col: int) -> None:
        sortie = self.table.item(ligne, 4).data(Qt.UserRole)
        if sortie:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(sortie).parent)))

    def closeEvent(self, ev):
        if self.fil and self.fil.isRunning():
            self.fil.wait()
        super().closeEvent(ev)


class DialogueExport(QDialog):
    """Choix des options puis export PDF de la vue courante."""

    def __init__(self, fenetre, parent=None):
        super().__init__(parent or fenetre)
        self.fenetre = fenetre
        self.setWindowTitle(t("export_titre"))
        self.vue = QComboBox()
        self.vue.addItem(t("vue_mois"), "mois")
        self.vue.addItem(t("vue_semaine"), "semaine")
        self.vue.setCurrentIndex(1 if fenetre.vue_semaine_active() else 0)
        self.compact = QCheckBox(t("vue_compact"))
        self.compact.setChecked(fenetre.vue_mois.compact)
        self.perso = QCheckBox(t("export_avec_perso"))
        self.perso.setChecked(True)
        self.vue.currentIndexChanged.connect(lambda: self.compact.setEnabled(self.vue.currentData() == "mois"))
        form = QFormLayout()
        form.addRow(t("export_vue"), self.vue)
        form.addRow("", self.compact)
        form.addRow("", self.perso)
        boutons = QDialogButtonBox()
        boutons.addButton(t("export_bouton"), QDialogButtonBox.AcceptRole)
        boutons.addButton(t("bouton_annuler"), QDialogButtonBox.RejectRole)
        boutons.accepted.connect(self._exporter)
        boutons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(boutons)

    def _exporter(self) -> None:
        from .export_pdf import exporter, nom_fichier
        vue = self.vue.currentData()
        jour: date = self.fenetre.jour
        defaut = Path.home() / "Documents" / nom_fichier(vue, jour)
        chemin, _ = QFileDialog.getSaveFileName(self, t("export_titre"), str(defaut), "PDF (*.pdf)")
        if not chemin:
            return
        try:
            exporter(self.fenetre.conn, chemin, vue, jour, compact=self.compact.isChecked(),
                     avec_perso=self.perso.isChecked(), ville=self.fenetre.donnees.ville,
                     expos_masquees=self.fenetre.donnees.expos_masquees)
        except Exception as exc:  # noqa: BLE001 — fichier ouvert ailleurs, droits…
            QMessageBox.warning(self, t("export_titre"), t("export_erreur", erreur=exc))
            return
        if os.name == "nt":
            QDesktopServices.openUrl(QUrl.fromLocalFile(chemin))
        self.accept()
