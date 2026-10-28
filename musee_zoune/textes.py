"""Textes affichés à l'utilisateur, en français et en allemand.

Utilisation : `t("sync_debut", url=...)`. Changer de langue : `choisir_langue("de")`.
Toute nouvelle clé doit être ajoutée dans les deux langues
(le test `test_textes.py` le vérifie).
"""

LANGUES = {"fr": "Français", "de": "Deutsch"}
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
        "sync_deja_faite": "Programmation déjà à jour (synchronisée aujourd'hui à {heure}).",
        "sync_bouton_actualiser": "Actualiser",
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
        # Application
        "app_titre": "Musée Zoune — programmation BLMK",
        "vue_mois": "Mois",
        "vue_semaine": "Semaine",
        "nav_precedent": "◀",
        "nav_suivant": "▶",
        "nav_aujourdhui": "Aujourd'hui",
        "langue": "Langue",
        "filtre_ville": "Lieu",
        "filtre_toutes_villes": "Tous les lieux",
        "statut_sync_en_cours": "Synchronisation en cours…",
        "statut_sync_ok": "Programmation à jour ({heure}).",
        "statut_sync_rien": "Programmation à jour (dernière synchronisation à {heure}).",
        "statut_hors_ligne": "Site injoignable : affichage des données du {date}.",
        "statut_jamais_sync": "Site injoignable et aucune donnée enregistrée pour l'instant.",
        "semaine_num": "Semaine {num} — du {debut} au {fin}",
        "plus_n": "+{n} autres",
        "toute_la_journee": "Journée",
        # Légende
        "legende_titre": "Expositions",
        "legende_aide": "Cliquer pour masquer / afficher",
        "legende_autres": "Autres événements",
        "legende_vie_perso": "Vie de Zoune",
        # Détails
        "details_titre": "Détails",
        "details_vide": "Cliquez sur un événement pour voir sa description.",
        "details_lieu": "Lieu",
        "details_quand": "Quand",
        "details_type": "Type",
        "details_statut": "Statut",
        "details_expo_liee": "Exposition liée",
        "details_fiche": "Voir la fiche sur le site",
        "details_modifier": "Modifier",
        # Changements
        "chg_titre": "Changements récents",
        "chg_aucun": "Rien de nouveau depuis votre dernière consultation.",
        "chg_marquer_lu": "Marquer comme lu",
        "chg_compteur": "Changements ({n})",
        "chg_bandeau": "{n} changement(s) dans la programmation depuis votre dernière consultation — cliquer pour voir",
        "chg_le": "le {date}",
        # Vie de Zoune
        "perso_titre": "Vie de Zoune",
        "perso_ajouter": "Ajouter…",
        "perso_gerer": "Vie de Zoune…",
        "perso_nouveau": "Nouvel élément",
        "perso_modifier": "Modifier l'élément",
        "perso_supprimer": "Supprimer",
        "perso_confirmer_suppr": "Supprimer « {titre} » ?",
        "perso_champ_titre": "Titre",
        "perso_champ_type": "Type",
        "perso_champ_debut": "Début",
        "perso_champ_fin": "Fin",
        "perso_champ_journee": "Journée entière",
        "perso_champ_note": "Note",
        "perso_titre_obligatoire": "Le titre est obligatoire.",
        "perso_fin_avant_debut": "La fin doit être après le début.",
        "perso_type_vacances": "Vacances",
        "perso_type_weekend": "Week-end",
        "perso_type_rdv": "Rendez-vous",
        "perso_type_autre": "Autre",
        "perso_liste_vide": "Aucun élément pour l'instant.",
        "bouton_ok": "Enregistrer",
        "bouton_annuler": "Annuler",
        "bouton_fermer": "Fermer",
        # Dates
        "mois": "janvier février mars avril mai juin juillet août septembre octobre novembre décembre",
        "jours_courts": "lun. mar. mer. jeu. ven. sam. dim.",
        "format_date": "{jour_sem} {j} {mois}",
        "format_date_longue": "{jour_sem} {j} {mois} {a}",
    },
    "de": {
        "type_exposition": "Ausstellung",
        "type_vernissage": "Eröffnung",
        "type_visite": "Führung",
        "type_atelier": "Workshop",
        "type_concert": "Konzert",
        "type_evenement": "Sonderveranstaltung",
        "type_annonce": "Ankündigung",
        "type_autre": "Sonstiges",
        "statut_prevu": "geplant",
        "statut_annule": "abgesagt",
        "statut_reporte": "verschoben",
        "statut_retire": "von der Website entfernt",
        "statut_passe": "vorbei",
        "chg_ajout": "Neu",
        "chg_modification": "Geändert",
        "chg_annulation": "Abgesagt",
        "sync_deja_faite": "Programm bereits aktuell (heute um {heure} synchronisiert).",
        "sync_bouton_actualiser": "Aktualisieren",
        "sync_debut": "Programm wird von {url} abgerufen…",
        "sync_source_api": "Quelle: API der Website ({n} Termine).",
        "sync_source_html": "Quelle: HTML-Seite des Kalenders ({n} Termine) – die API hat nicht geantwortet.",
        "sync_erreur_api": "Die API hat nicht geantwortet ({erreur}). Wechsel auf die HTML-Seite.",
        "sync_erreur_totale": "Programm konnte nicht abgerufen werden: {erreur}",
        "sync_trop_peu": (
            "Achtung: nur {n} Termine abgerufen, erwartet wurden {actifs}. "
            "Vorsichtshalber wird bei dieser Synchronisation nichts als abgesagt markiert."
        ),
        "sync_resume_titre": "Zusammenfassung der Synchronisation ({date})",
        "sync_resume": (
            "{total} kommende Termine auf der Website – "
            "{ajouts} neu, {modifs} geändert, {annulations} abgesagt, {passes} vorbei."
        ),
        "sync_rien": "Keine Änderungen seit der letzten Synchronisation.",
        "sync_simulation": "(Simulation: nichts wurde gespeichert.)",
        "motif_statut_site": "auf der Website als „{statut}“ markiert",
        "motif_disparu": "erscheint nicht mehr im Kalender der Website",
        "motif_reapparu": "wieder im Kalender erschienen",
        "champ_title": "Titel",
        "champ_type": "Art",
        "champ_start": "Beginn",
        "champ_end": "Ende",
        "champ_venue": "Ort",
        "champ_city": "Stadt",
        "champ_description": "Beschreibung",
        "champ_status": "Status",
        "champ_image": "Bild",
        "champ_categories": "Kategorien",
        "app_titre": "Musée Zoune – Programm BLMK",
        "vue_mois": "Monat",
        "vue_semaine": "Woche",
        "nav_precedent": "◀",
        "nav_suivant": "▶",
        "nav_aujourdhui": "Heute",
        "langue": "Sprache",
        "filtre_ville": "Ort",
        "filtre_toutes_villes": "Alle Orte",
        "statut_sync_en_cours": "Synchronisierung läuft…",
        "statut_sync_ok": "Programm aktuell ({heure}).",
        "statut_sync_rien": "Programm aktuell (letzte Synchronisierung um {heure}).",
        "statut_hors_ligne": "Website nicht erreichbar: Daten vom {date} werden angezeigt.",
        "statut_jamais_sync": "Website nicht erreichbar und noch keine Daten gespeichert.",
        "semaine_num": "KW {num} – {debut} bis {fin}",
        "plus_n": "+{n} weitere",
        "toute_la_journee": "Ganztägig",
        "legende_titre": "Ausstellungen",
        "legende_aide": "Klicken zum Aus-/Einblenden",
        "legende_autres": "Weitere Termine",
        "legende_vie_perso": "Zounes Leben",
        "details_titre": "Details",
        "details_vide": "Auf einen Termin klicken, um die Beschreibung zu sehen.",
        "details_lieu": "Ort",
        "details_quand": "Wann",
        "details_type": "Art",
        "details_statut": "Status",
        "details_expo_liee": "Zugehörige Ausstellung",
        "details_fiche": "Seite auf der Website öffnen",
        "details_modifier": "Bearbeiten",
        "chg_titre": "Letzte Änderungen",
        "chg_aucun": "Nichts Neues seit Ihrem letzten Besuch.",
        "chg_marquer_lu": "Als gelesen markieren",
        "chg_compteur": "Änderungen ({n})",
        "chg_bandeau": "{n} Änderung(en) im Programm seit Ihrem letzten Besuch – zum Ansehen klicken",
        "chg_le": "am {date}",
        "perso_titre": "Zounes Leben",
        "perso_ajouter": "Hinzufügen…",
        "perso_gerer": "Zounes Leben…",
        "perso_nouveau": "Neuer Eintrag",
        "perso_modifier": "Eintrag bearbeiten",
        "perso_supprimer": "Löschen",
        "perso_confirmer_suppr": "„{titre}“ löschen?",
        "perso_champ_titre": "Titel",
        "perso_champ_type": "Art",
        "perso_champ_debut": "Beginn",
        "perso_champ_fin": "Ende",
        "perso_champ_journee": "Ganztägig",
        "perso_champ_note": "Notiz",
        "perso_titre_obligatoire": "Der Titel ist erforderlich.",
        "perso_fin_avant_debut": "Das Ende muss nach dem Beginn liegen.",
        "perso_type_vacances": "Urlaub",
        "perso_type_weekend": "Wochenende",
        "perso_type_rdv": "Termin",
        "perso_type_autre": "Sonstiges",
        "perso_liste_vide": "Noch keine Einträge.",
        "bouton_ok": "Speichern",
        "bouton_annuler": "Abbrechen",
        "bouton_fermer": "Schließen",
        "mois": "Januar Februar März April Mai Juni Juli August September Oktober November Dezember",
        "jours_courts": "Mo. Di. Mi. Do. Fr. Sa. So.",
        "format_date": "{jour_sem} {j}. {mois}",
        "format_date_longue": "{jour_sem} {j}. {mois} {a}",
    },
}


def choisir_langue(code: str) -> None:
    global LANGUE
    if code in TEXTES:
        LANGUE = code


def t(cle: str, **valeurs) -> str:
    """Renvoie le texte `cle` dans la langue courante (repli sur le français)."""
    texte = TEXTES.get(LANGUE, {}).get(cle) or TEXTES["fr"].get(cle, cle)
    return texte.format(**valeurs) if valeurs else texte


def nom_mois(numero: int) -> str:
    return t("mois").split()[numero - 1]


def jour_court(index_lundi0: int) -> str:
    return t("jours_courts").split()[index_lundi0]


def date_lisible(d, longue: bool = False) -> str:
    return t("format_date_longue" if longue else "format_date",
             jour_sem=jour_court(d.weekday()), j=d.day, mois=nom_mois(d.month), a=d.year)
