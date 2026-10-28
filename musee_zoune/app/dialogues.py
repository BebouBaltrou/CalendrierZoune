"""Fenêtres de saisie de la « Vie de Zoune »."""

from __future__ import annotations

from datetime import date, datetime, time

from PySide6.QtCore import QDate, QDateTime, QTime, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)

from .. import calendrier as cal
from .. import db
from ..textes import date_lisible, t


def _qdt(valeur: datetime) -> QDateTime:
    return QDateTime(QDate(valeur.year, valeur.month, valeur.day), QTime(valeur.hour, valeur.minute))


def _py(qdt: QDateTime) -> datetime:
    d, h = qdt.date(), qdt.time()
    return datetime(d.year(), d.month(), d.day(), h.hour(), h.minute())


class DialoguePerso(QDialog):
    """Ajout ou modification d'un élément de vie perso."""

    def __init__(self, conn, parent=None, element: dict | None = None,
                 debut: datetime | None = None, journee: bool = True):
        super().__init__(parent)
        self.conn, self.element = conn, element
        self.setWindowTitle(t("perso_modifier" if element else "perso_nouveau"))
        self.setMinimumWidth(380)

        self.titre = QLineEdit()
        self.type = QComboBox()
        for code in db.TYPES_PERSO:
            self.type.addItem(t("perso_type_" + code), code)
        self.journee = QCheckBox(t("perso_champ_journee"))
        self.debut, self.fin = QDateTimeEdit(), QDateTimeEdit()
        for champ in (self.debut, self.fin):
            champ.setCalendarPopup(True)
        self.note = QTextEdit()
        self.note.setFixedHeight(60)

        if element:
            self.titre.setText(element["titre"])
            self.type.setCurrentIndex(max(0, self.type.findData(element["type"])))
            self.journee.setChecked(element["journee"])
            self.debut.setDateTime(_qdt(cal.dt(element["debut"])))
            self.fin.setDateTime(_qdt(cal.dt(element["fin"])))
            self.note.setPlainText(element.get("note", ""))
        else:
            debut = debut or datetime.combine(date.today(), time(9, 0))
            self.journee.setChecked(journee)
            self.type.setCurrentIndex(self.type.findData("autre" if journee else "rdv"))
            self.debut.setDateTime(_qdt(debut))
            fin = debut.replace(hour=min(debut.hour + 1, 23)) if not journee else debut
            self.fin.setDateTime(_qdt(fin))
        self.journee.toggled.connect(self._format)
        self._format(self.journee.isChecked())

        form = QFormLayout()
        form.addRow(t("perso_champ_titre"), self.titre)
        form.addRow(t("perso_champ_type"), self.type)
        form.addRow("", self.journee)
        form.addRow(t("perso_champ_debut"), self.debut)
        form.addRow(t("perso_champ_fin"), self.fin)
        form.addRow(t("perso_champ_note"), self.note)

        boutons = QDialogButtonBox()
        boutons.addButton(t("bouton_ok"), QDialogButtonBox.AcceptRole)
        boutons.addButton(t("bouton_annuler"), QDialogButtonBox.RejectRole)
        if element:
            suppr = boutons.addButton(t("perso_supprimer"), QDialogButtonBox.DestructiveRole)
            suppr.clicked.connect(self._supprimer)
        boutons.accepted.connect(self._enregistrer)
        boutons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(boutons)
        self.titre.setFocus()

    def _format(self, journee: bool) -> None:
        fmt = "dd/MM/yyyy" if journee else "dd/MM/yyyy HH:mm"
        for champ in (self.debut, self.fin):
            champ.setDisplayFormat(fmt)

    def _enregistrer(self) -> None:
        titre = self.titre.text().strip()
        debut, fin = _py(self.debut.dateTime()), _py(self.fin.dateTime())
        journee = self.journee.isChecked()
        if journee:
            debut, fin = datetime.combine(debut.date(), time(0, 0)), datetime.combine(fin.date(), time(23, 59))
        if not titre:
            QMessageBox.warning(self, self.windowTitle(), t("perso_titre_obligatoire"))
            return
        if fin < debut:
            QMessageBox.warning(self, self.windowTitle(), t("perso_fin_avant_debut"))
            return
        valeurs = (titre, self.type.currentData(), debut.isoformat(timespec="minutes"),
                   fin.isoformat(timespec="minutes"), journee, self.note.toPlainText())
        if self.element:
            db.modifier_perso(self.conn, self.element["id"], *valeurs)
        else:
            db.ajouter_perso(self.conn, *valeurs)
        self.accept()

    def _supprimer(self) -> None:
        reponse = QMessageBox.question(self, self.windowTitle(),
                                       t("perso_confirmer_suppr", titre=self.element["titre"]))
        if reponse == QMessageBox.Yes:
            db.supprimer_perso(self.conn, self.element["id"])
            self.accept()


class ListePerso(QDialog):
    """Liste de tous les éléments de vie perso, avec ajout / modification / suppression."""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.modifie = False
        self.setWindowTitle(t("perso_titre"))
        self.resize(520, 420)
        self.liste = QListWidget()
        self.liste.itemDoubleClicked.connect(self._modifier)

        ajouter = QPushButton(t("perso_ajouter"))
        modifier = QPushButton(t("details_modifier"))
        supprimer = QPushButton(t("perso_supprimer"))
        fermer = QPushButton(t("bouton_fermer"))
        ajouter.clicked.connect(self._ajouter)
        modifier.clicked.connect(lambda: self._modifier(self.liste.currentItem()))
        supprimer.clicked.connect(self._supprimer)
        fermer.clicked.connect(self.accept)

        boutons = QHBoxLayout()
        for b in (ajouter, modifier, supprimer):
            boutons.addWidget(b)
        boutons.addStretch()
        boutons.addWidget(fermer)
        layout = QVBoxLayout(self)
        layout.addWidget(self.liste)
        layout.addLayout(boutons)
        self._remplir()

    def _remplir(self) -> None:
        self.liste.clear()
        elements = db.tout_perso(self.conn)
        if not elements:
            item = QListWidgetItem(t("perso_liste_vide"))
            item.setFlags(Qt.NoItemFlags)
            self.liste.addItem(item)
        for p in elements:
            debut, fin = cal.dt(p["debut"]), cal.dt(p["fin"])
            quand = date_lisible(debut.date(), longue=True)
            if fin.date() != debut.date():
                quand += " → " + date_lisible(fin.date(), longue=True)
            if not p["journee"]:
                quand += f"  {debut:%H:%M}–{fin:%H:%M}"
            item = QListWidgetItem(f"{p['titre']}  —  {t('perso_type_' + p['type'])}  —  {quand}")
            item.setData(Qt.UserRole, p["id"])
            item.setForeground(QColor(cal.COULEUR_PERSO))
            self.liste.addItem(item)

    def _ajouter(self) -> None:
        if DialoguePerso(self.conn, self).exec():
            self.modifie = True
            self._remplir()

    def _modifier(self, item) -> None:
        if not item or item.data(Qt.UserRole) is None:
            return
        element = db.lire_perso(self.conn, item.data(Qt.UserRole))
        if element and DialoguePerso(self.conn, self, element=element).exec():
            self.modifie = True
            self._remplir()

    def _supprimer(self) -> None:
        item = self.liste.currentItem()
        if not item or item.data(Qt.UserRole) is None:
            return
        element = db.lire_perso(self.conn, item.data(Qt.UserRole))
        reponse = QMessageBox.question(self, self.windowTitle(),
                                       t("perso_confirmer_suppr", titre=element["titre"]))
        if reponse == QMessageBox.Yes:
            db.supprimer_perso(self.conn, element["id"])
            self.modifie = True
            self._remplir()
