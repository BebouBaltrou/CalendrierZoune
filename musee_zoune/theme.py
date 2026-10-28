"""Toutes les couleurs et polices de l'interface, au même endroit.

Deux thèmes : SOMBRE (l'application, façon Google Agenda en mode sombre) et CLAIR
(export PDF, pour ne pas imprimer de grands aplats noirs).
Les couleurs des expositions (`PALETTE`) sont communes aux deux.
"""

from __future__ import annotations

from dataclasses import dataclass

POLICE = "Segoe UI"  # repli automatique de Qt sur Roboto / police système

# Couleurs des expositions : tons soutenus, lisibles en texte blanc sur fond sombre.
# L'ordre compte : la base mémorise l'index attribué à chaque exposition.
PALETTE = [
    "#E67C73", "#039BE5", "#33B679", "#D81B60", "#F4B400", "#7986CB", "#F4511E",
    "#009688", "#A1887F", "#8E24AA", "#EF6C00", "#3F51B5", "#0B8043", "#AD1457",
]

# Événements sans exposition liée : gris bleutés selon le type.
COULEURS_TYPES = {
    "atelier": "#5F6368",
    "visite": "#5B6B7F",
    "vernissage": "#7A5C61",
    "concert": "#6E6250",
    "evenement": "#665A78",
    "annonce": "#5F6368",
    "autre": "#5F6368",
    "exposition": "#5F6368",
}

COULEUR_PERSO = "#C58AF9"        # bord pointillé de la Vie de Zoune
COULEUR_ACCENT = "#8AB4F8"       # bleu Google (jour courant, liens, sélection)
COULEUR_FAB = "#F28B82"          # bouton « + » flottant
COULEUR_SANS_POST = "#FF8A50"
COULEUR_POSTIT = "#FDD663"       # post-it des posts dans le calendrier
COULEUR_POSTIT_PLI = "#E2B93B"
COULEUR_POST_PREVU = "#8AB4F8"
COULEUR_POST_PUBLIE = "#81C995"
COULEUR_ANNULE = "#F28B82"
COULEUR_CHANGEMENT = {"ajout": "#81C995", "modification": "#FDD663", "annulation": "#F28B82"}


@dataclass(frozen=True)
class Theme:
    fond: str
    fond_panneau: str
    fond_survol: str
    fond_saisie: str
    grille: str
    texte: str
    texte_secondaire: str
    texte_attenue: str
    perso_fond: str
    aujourdhui_texte: str
    sombre: bool


SOMBRE = Theme(
    fond="#202124",
    fond_panneau="#202124",
    fond_survol="#303134",
    fond_saisie="#303134",
    grille="#3C4043",
    texte="#E8EAED",
    texte_secondaire="#9AA0A6",
    texte_attenue="#5F6368",
    perso_fond="#3B2F4F",
    aujourdhui_texte="#202124",
    sombre=True,
)

CLAIR = Theme(
    fond="#FFFFFF",
    fond_panneau="#FFFFFF",
    fond_survol="#F1F3F4",
    fond_saisie="#F1F3F4",
    grille="#DADCE0",
    texte="#202124",
    texte_secondaire="#5F6368",
    texte_attenue="#B0B4B8",
    perso_fond="#F3E8FD",
    aujourdhui_texte="#FFFFFF",
    sombre=False,
)


def luminance(hex_couleur: str) -> float:
    """Luminance relative (WCAG) d'une couleur #RRGGBB."""
    canaux = []
    for i in (1, 3, 5):
        c = int(hex_couleur[i:i + 2], 16) / 255
        canaux.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = canaux
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def texte_sur(fond: str) -> str:
    """Blanc sur les couleurs soutenues, gris très foncé sur les couleurs claires."""
    return "#FFFFFF" if contraste(fond, "#FFFFFF") >= contraste(fond, "#202124") * 0.55 else "#202124"


def feuille_de_style(th: Theme = SOMBRE) -> str:
    """Feuille de style Qt (QSS) de toute l'application."""
    return f"""
    QWidget {{
        background: {th.fond}; color: {th.texte};
        font-family: "{POLICE}", "Roboto", sans-serif; font-size: 10pt;
    }}
    QToolTip {{
        background: #3C4043; color: #E8EAED; border: none; padding: 4px 8px; border-radius: 4px;
    }}
    QPushButton {{
        background: transparent; border: 1px solid {th.grille}; border-radius: 18px;
        padding: 6px 16px; color: {th.texte};
    }}
    QPushButton:hover {{ background: {th.fond_survol}; }}
    QPushButton:disabled {{ color: {th.texte_attenue}; border-color: {th.fond_survol}; }}
    QPushButton:default {{ background: {COULEUR_ACCENT}; color: #202124; border: none; }}
    QToolButton {{
        background: transparent; border: none; border-radius: 18px; padding: 6px 10px;
        color: {th.texte};
    }}
    QToolButton:hover {{ background: {th.fond_survol}; }}
    QToolButton:checked {{ background: #394457; color: {COULEUR_ACCENT}; }}
    QToolButton::menu-indicator {{ image: none; width: 0; }}
    QLineEdit, QTextEdit, QSpinBox, QDateEdit, QDateTimeEdit, QComboBox {{
        background: {th.fond_saisie}; border: 1px solid transparent; border-radius: 6px;
        padding: 5px 8px; color: {th.texte}; selection-background-color: {COULEUR_ACCENT};
        selection-color: #202124;
    }}
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus,
    QDateEdit:focus, QDateTimeEdit:focus {{ border: 1px solid {COULEUR_ACCENT}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView, QMenu {{
        background: #2D2E31; color: {th.texte}; border: 1px solid {th.grille};
        selection-background-color: {th.fond_survol}; selection-color: {th.texte}; padding: 4px;
    }}
    QMenu::item {{ padding: 7px 24px 7px 14px; border-radius: 4px; }}
    QMenu::item:selected {{ background: #3C4043; }}
    QMenu::item:disabled {{ color: {th.texte_attenue}; }}
    QMenu::separator {{ height: 1px; background: {th.grille}; margin: 4px 8px; }}
    QListWidget, QTableWidget, QTextBrowser {{
        background: {th.fond}; border: none; outline: none;
    }}
    QListWidget::item {{ padding: 6px 4px; border-radius: 6px; }}
    QListWidget QScrollBar:horizontal {{ height: 0; }}
    QListWidget::item:selected, QTableWidget::item:selected {{
        background: #394457; color: {th.texte};
    }}
    QListWidget::item:hover {{ background: {th.fond_survol}; }}
    QHeaderView::section {{
        background: {th.fond}; color: {th.texte_secondaire}; border: none;
        border-bottom: 1px solid {th.grille}; padding: 6px;
    }}
    QTableWidget {{ gridline-color: {th.grille}; }}
    QTabWidget::pane {{ border: none; border-top: 1px solid {th.grille}; }}
    QTabBar::tab {{
        background: transparent; color: {th.texte_secondaire}; padding: 8px 12px;
        border: none; border-bottom: 3px solid transparent;
    }}
    QTabBar::tab:selected {{ color: {COULEUR_ACCENT}; border-bottom: 3px solid {COULEUR_ACCENT}; }}
    QTabBar::tab:hover {{ color: {th.texte}; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
    QScrollBar::handle {{ background: #5F6368; border-radius: 5px; min-height: 30px; min-width: 30px; }}
    QScrollBar::handle:hover {{ background: #80868B; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px; border: 2px solid {th.texte_secondaire}; border-radius: 3px;
    }}
    QCheckBox::indicator:checked {{ background: {COULEUR_ACCENT}; border-color: {COULEUR_ACCENT}; }}
    QDialog {{ background: #2D2E31; }}
    QDialog QWidget {{ background: #2D2E31; }}
    QDialog QLineEdit, QDialog QTextEdit, QDialog QSpinBox, QDialog QComboBox,
    QDialog QDateEdit, QDialog QDateTimeEdit {{ background: #3C4043; }}
    QDialog QListWidget, QDialog QTableWidget {{ background: #2D2E31; }}
    QMessageBox QLabel {{ background: transparent; }}
    QCalendarWidget QWidget {{ background: #2D2E31; }}
    QSplitter::handle {{ background: {th.grille}; }}
    """
