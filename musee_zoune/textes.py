"""Textes affichés à l'utilisateur, regroupés pour la future version bilingue FR/DE.

Utilisation : `t("sync_debut")` ou `t("sync_resume", ajouts=3, ...)`.
Pour ajouter l'allemand, remplir TEXTES["de"] avec les mêmes clés.
"""

LANGUE = "fr"

TEXTES = {
    "fr": {
        # Types d'événements
        "type_exposition": "Exposition",
        "type_vernissage": "Vernissage",
        "type_visite": "Visite guidée",
        "type_atelier": "Atelier",
        "type_concert": "Concert",
        "type_evenement": "Événement spécial",
        "type_annonce": "Annonce",
        "type_autre": "Autre",
        # Statuts
        "statut_prevu": "prévu",
        "statut_annule": "annulé",
        "statut_reporte": "reporté",
        "statut_retire": "retiré du site",
        "statut_passe": "passé",
        # Types de changements
        "chg_ajout": "Ajout",
        "chg_modification": "Modification",
        "chg_annulation": "Annulation",
        # Synchronisation
        "sync_debut": "Récupération de la programmation sur {url}…",
        "sync_source_api": "Source : API du site ({n} événements).",
        "sync_source_html": "Source : page HTML du calendrier ({n} événements) — l'API n'a pas répondu.",
        "sync_erreur_api": "L'API n'a pas répondu ({erreur}). Bascule sur la page HTML.",
        "sync_erreur_totale": "Impossible de récupérer la programmation : {erreur}",
        "sync_trop_peu": (
            "Attention : seulement {n} événements récupérés alors que {actifs} sont attendus. "
            "Par prudence, aucun événement n'est marqué comme annulé lors de cette synchronisation."
        ),
        "sync_resume_titre": "Résumé de la synchronisation ({date})",
        "sync_resume": (
            "{total} événements à venir sur le site — "
            "{ajouts} ajout(s), {modifs} modification(s), {annulations} annulation(s), "
            "{passes} passé(s)."
        ),
        "sync_rien": "Aucun changement depuis la dernière synchronisation.",
        "sync_simulation": "(Simulation : rien n'a été enregistré.)",
        "motif_statut_site": "marqué « {statut} » sur le site",
        "motif_disparu": "n'apparaît plus dans le calendrier du site",
        "motif_reapparu": "réapparu dans le calendrier",
        # Noms des champs (pour décrire les modifications)
        "champ_title": "titre",
        "champ_type": "type",
        "champ_start": "début",
        "champ_end": "fin",
        "champ_venue": "lieu",
        "champ_city": "ville",
        "champ_description": "description",
        "champ_status": "statut",
        "champ_image": "image",
        "champ_categories": "catégories",
    },
    "de": {},
}


def t(cle: str, **valeurs) -> str:
    """Renvoie le texte `cle` dans la langue courante (repli sur le français)."""
    texte = TEXTES.get(LANGUE, {}).get(cle) or TEXTES["fr"].get(cle, cle)
    return texte.format(**valeurs) if valeurs else texte
