"""Fenêtres de saisie de la « Vie de Zoune »."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QDate, QDateTime, QTime, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDateTimeEdit, QDialog, QLabel, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTextEdit, QTimeEdit, QVBoxLayout,
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


class DialoguePost(QDialog):
    """Création / modification d'un post, lié à zéro, un ou plusieurs événements."""

    def __init__(self, conn, parent=None, post: dict | None = None, precoches=()):
        super().__init__(parent)
        self.conn, self.post = conn, post
        self.setWindowTitle(t("post_modifier" if post else "post_nouveau"))
        self.resize(560, 640)

        self.titre = QLineEdit()
        self.titre.setPlaceholderText(t("post_titre_aide"))
        self.reseau = QComboBox()
        for code in db.RESEAUX:
            self.reseau.addItem(t("reseau_" + code), code)
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd/MM/yyyy")
        self.avec_heure = QCheckBox(t("post_avec_heure"))
        self.heure = QTimeEdit(QTime(10, 0))
        self.heure.setDisplayFormat("HH:mm")
        self.avec_heure.toggled.connect(self.heure.setEnabled)
        self.heure.setEnabled(False)
        self.statut = QComboBox()
        for code in db.STATUTS_POST:
            self.statut.addItem(t("post_statut_" + code), code)
        self.note = QTextEdit()
        self.note.setFixedHeight(60)

        coches = set(post["evenements"]) if post else set(precoches)
        if post:
            self.titre.setText(post.get("titre", ""))
            self.reseau.setCurrentIndex(max(0, self.reseau.findData(post["reseau"])))
            jour = date.fromisoformat(post["date"][:10])
            if len(post["date"]) > 10:
                self.avec_heure.setChecked(True)
                h, m = post["date"][11:16].split(":")
                self.heure.setTime(QTime(int(h), int(m)))
            self.statut.setCurrentIndex(max(0, self.statut.findData(post["statut"])))
            self.note.setPlainText(post.get("note", ""))
        else:
            jour = date.today()
            premiers = [cal.dt(r[0]).date() for r in conn.execute(
                f"SELECT start FROM events WHERE uid IN ({','.join('?' * len(coches))})", list(coches))]                 if coches else []
            if premiers:  # par défaut : une semaine avant le premier événement coché
                jour = max(date.today(), min(premiers) - timedelta(days=7))
        self.date.setDate(QDate(jour.year, jour.month, jour.day))

        # événements à cocher
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText(t("post_recherche_evenement"))
        self.recherche.textChanged.connect(self._filtrer)
        self.liste = QListWidget()
        self.liste.itemChanged.connect(self._compter)
        self.liste.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.liste.setTextElideMode(Qt.ElideRight)
        self.compteur = QLabel()
        self.compteur.setStyleSheet("color:#9AA0A6;")
        limite = (date.today() - timedelta(days=60)).isoformat()
        lignes = conn.execute(
            """SELECT uid, title, type, start, end, city FROM events
               WHERE status != 'retire' AND (COALESCE(NULLIF(end, ''), start) >= ? OR uid IN (%s))
               ORDER BY start""" % ",".join("?" * len(coches)) if coches else
            """SELECT uid, title, type, start, end, city FROM events
               WHERE status != 'retire' AND COALESCE(NULLIF(end, ''), start) >= ? ORDER BY start""",
            [limite, *coches] if coches else [limite])
        self.liste.blockSignals(True)
        for r in lignes:
            debut = cal.dt(r["start"])
            texte = f"{debut:%d/%m/%Y}  {r['title']}  ·  {t('type_' + r['type'])}"
            if r["city"]:
                texte += f" · {r['city']}"
            item = QListWidgetItem(texte)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if r["uid"] in coches else Qt.Unchecked)
            item.setData(Qt.UserRole, r["uid"])
            item.setData(Qt.UserRole + 1, cal.normaliser(texte))
            self.liste.addItem(item)
        self.liste.blockSignals(False)
        self._compter()
        premier_coche = next((self.liste.item(i) for i in range(self.liste.count())
                              if self.liste.item(i).checkState() == Qt.Checked), None)
        if premier_coche:
            self.liste.scrollToItem(premier_coche, QListWidget.PositionAtCenter)

        form = QFormLayout()
        form.addRow(t("post_champ_titre"), self.titre)
        form.addRow(t("post_champ_reseau"), self.reseau)
        form.addRow(t("post_champ_date"), self.date)
        ligne_heure = QHBoxLayout()
        ligne_heure.addWidget(self.avec_heure)
        ligne_heure.addWidget(self.heure)
        ligne_heure.addStretch()
        form.addRow(t("post_champ_heure"), ligne_heure)
        form.addRow(t("post_champ_statut"), self.statut)
        form.addRow(t("post_champ_note"), self.note)
        titre_ev = QLabel(t("post_evenements"))
        titre_ev.setStyleSheet("font-weight:600; padding-top:8px;")

        boutons = QDialogButtonBox()
        boutons.addButton(t("bouton_ok"), QDialogButtonBox.AcceptRole).setDefault(True)
        boutons.addButton(t("bouton_annuler"), QDialogButtonBox.RejectRole)
        boutons.accepted.connect(self._enregistrer)
        boutons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(titre_ev)
        layout.addWidget(self.recherche)
        layout.addWidget(self.liste, 1)
        layout.addWidget(self.compteur)
        layout.addWidget(boutons)

    def evenements_coches(self) -> list[str]:
        return [self.liste.item(i).data(Qt.UserRole) for i in range(self.liste.count())
                if self.liste.item(i).checkState() == Qt.Checked]

    def _filtrer(self, texte: str) -> None:
        mots = cal.normaliser(texte).split()
        for i in range(self.liste.count()):
            item = self.liste.item(i)
            cible = item.data(Qt.UserRole + 1)
            item.setHidden(bool(mots) and not all(m in cible for m in mots))

    def _compter(self, *_):
        n = len(self.evenements_coches())
        self.compteur.setText(t("post_n_coches", n=n) if n else t("post_aucun_coche"))

    def _enregistrer(self) -> None:
        d = self.date.date()
        jour = date(d.year(), d.month(), d.day()).isoformat()
        if self.avec_heure.isChecked():
            jour += "T" + self.heure.time().toString("HH:mm")
        valeurs = dict(reseau=self.reseau.currentData(), date_=jour, statut=self.statut.currentData(),
                       note=self.note.toPlainText(), titre=self.titre.text(),
                       evenements=self.evenements_coches())
        if self.post:
            db.modifier_post(self.conn, self.post["id"], **valeurs)
        else:
            db.ajouter_post(self.conn, **valeurs)
        self.accept()
