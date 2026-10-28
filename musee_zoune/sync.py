"""Synchronise la programmation du site avec la base locale.

Usage :
    python -m musee_zoune.sync              # synchronisation (bouton « Actualiser »)
    python -m musee_zoune.sync --si-necessaire  # seulement si pas encore faite aujourd'hui
    python -m musee_zoune.sync --simulation # affiche les changements sans rien enregistrer
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import datetime

from . import config, db
from .scraper import Evenement, recuperer_programmation
from .textes import t

log = logging.getLogger("musee_zoune.sync")


def _fin(ev: dict) -> str:
    return ev.get("end") or ev.get("start") or ""


def synchroniser(
    conn: sqlite3.Connection,
    scrapes: list[Evenement],
    source: str,
    maintenant: datetime | None = None,
    simulation: bool = False,
) -> dict:
    """Compare `scrapes` avec la base, enregistre les changements, renvoie un résumé."""
    maintenant = maintenant or datetime.now()
    horodatage = maintenant.isoformat(timespec="seconds")
    seuil_passe = maintenant.strftime("%Y-%m-%dT%H:%M")
    connus = db.evenements(conn)
    vus = {ev.uid: ev.as_dict() for ev in scrapes}

    resume = {"total": len(vus), "source": source, "ajouts": [], "modifications": [],
              "annulations": [], "passes": [], "prudence": False}

    for uid, ev in vus.items():
        ancien = connus.get(uid)
        if ancien is None:
            db.inserer(conn, ev, horodatage)
            db.noter_changement(conn, uid, "ajout", {}, horodatage)
            resume["ajouts"].append(ev)
            continue

        diff = {c: [ancien[c], ev[c]] for c in db.CHAMPS_SUIVIS if ancien[c] != ev[c]}
        # Un événement retiré/passé qui revient ne compte pas comme changement de statut
        # s'il revient « prévu » : on le signale par un motif.
        if ancien["status"] in ("retire", "passe") and ev["status"] == "prevu":
            diff.pop("status", None)
            if ancien["status"] == "retire":
                diff["motif"] = t("motif_reapparu")
        db.mettre_a_jour(conn, ev, horodatage, modifie=bool(diff))
        if not diff:
            continue
        if ev["status"] == "annule" and ancien["status"] != "annule":
            diff["motif"] = t("motif_statut_site", statut=t("statut_annule"))
            db.noter_changement(conn, uid, "annulation", diff, horodatage)
            resume["annulations"].append({**ev, "details": diff})
        else:
            db.noter_changement(conn, uid, "modification", diff, horodatage)
            resume["modifications"].append({**ev, "details": diff})

    # Événements connus absents du site
    absents = [e for uid, e in connus.items() if uid not in vus and e["status"] in db.ACTIFS]
    attendus = [e for e in absents if _fin(e) >= seuil_passe] + \
               [e for uid, e in connus.items() if uid in vus and e["status"] in db.ACTIFS]
    prudence = bool(connus) and len(vus) < config.SEUIL_PRUDENCE * len(attendus)
    resume["prudence"] = prudence
    resume["attendus"] = len(attendus)

    for ev in absents:
        if _fin(ev) < seuil_passe:
            db.changer_statut(conn, ev["uid"], "passe", horodatage)
            resume["passes"].append(ev)
        elif not prudence:
            db.changer_statut(conn, ev["uid"], "retire", horodatage)
            if ev["status"] != "annule":
                details = {"status": [ev["status"], "retire"], "motif": t("motif_disparu")}
                db.noter_changement(conn, ev["uid"], "annulation", details, horodatage)
                resume["annulations"].append({**ev, "details": details})

    resume_court = {k: len(v) if isinstance(v, list) else v for k, v in resume.items()}
    db.noter_sync(conn, horodatage, source, len(vus), resume_court)

    if simulation:
        conn.rollback()
    else:
        conn.commit()
    return resume


# --------------------------------------------------------------------------
# Affichage
# --------------------------------------------------------------------------

def _date_courte(iso: str) -> str:
    if not iso:
        return "?"
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%d/%m/%Y %H:%M").replace(" 00:00", "")


def _ligne(ev: dict) -> str:
    periode = _date_courte(ev["start"])
    if ev.get("end") and ev["end"][:10] != ev["start"][:10]:
        periode += f" → {_date_courte(ev['end'])}"
    lieu = ", ".join(x for x in (ev.get("venue"), ev.get("city")) if x)
    return f"  • [{t('type_' + ev['type'])}] {ev['title']} — {periode}" + (f" — {lieu}" if lieu else "")


def _details(diff: dict) -> list[str]:
    lignes = []
    for champ, valeur in diff.items():
        if champ == "motif":
            lignes.append(f"      ({valeur})")
        elif champ in ("description", "image", "categories"):
            lignes.append(f"      {t('champ_' + champ)} modifié(e)")
        else:
            avant, apres = valeur
            lignes.append(f"      {t('champ_' + champ)} : {avant} → {apres}")
    return lignes


def formater_resume(resume: dict, maintenant: datetime) -> str:
    lignes = [t("sync_resume_titre", date=maintenant.strftime("%d/%m/%Y %H:%M")),
              t("sync_resume", total=resume["total"], ajouts=len(resume["ajouts"]),
                modifs=len(resume["modifications"]), annulations=len(resume["annulations"]),
                passes=len(resume["passes"]))]
    if resume["prudence"]:
        lignes.append(t("sync_trop_peu", n=resume["total"], actifs=resume["attendus"]))
    for cle, titre in (("ajouts", "chg_ajout"), ("modifications", "chg_modification"),
                       ("annulations", "chg_annulation")):
        if resume[cle]:
            lignes.append(f"\n{t(titre)} ({len(resume[cle])}) :")
            for ev in sorted(resume[cle], key=lambda e: e["start"]):
                lignes.append(_ligne(ev))
                lignes += _details(ev.get("details", {}))
    if not (resume["ajouts"] or resume["modifications"] or resume["annulations"]):
        lignes.append(t("sync_rien"))
    return "\n".join(lignes)


def configurer_journal() -> None:
    config.DOSSIER_DONNEES.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(config.CHEMIN_JOURNAL, encoding="utf-8")],
    )


def derniere_sync(conn: sqlite3.Connection) -> datetime | None:
    """Date de la dernière synchronisation réussie (None si jamais)."""
    ligne = conn.execute("SELECT MAX(at) FROM sync_runs").fetchone()
    return datetime.fromisoformat(ligne[0]) if ligne and ligne[0] else None


def sync_necessaire(conn: sqlite3.Connection, maintenant: datetime | None = None) -> bool:
    """Vrai si aucune synchronisation réussie n'a eu lieu aujourd'hui."""
    maintenant = maintenant or datetime.now()
    derniere = derniere_sync(conn)
    return derniere is None or derniere.date() < maintenant.date()


def lancer_sync(forcer: bool = True, simulation: bool = False, afficher=print) -> dict | None:
    """Point d'entrée commun à la ligne de commande et à l'application.

    - Au démarrage de l'application : `lancer_sync(forcer=False)` -> ne fait
      rien si une synchronisation a déjà réussi aujourd'hui.
    - Bouton « Actualiser » : `lancer_sync(forcer=True)`.
    Renvoie le résumé, ou None si rien n'a été fait. Lève une exception si le
    site est injoignable (rien n'est enregistré : on réessaiera au prochain lancement).
    """
    conn = db.connecter()
    try:
        if not forcer and not sync_necessaire(conn):
            derniere = derniere_sync(conn)
            afficher(t("sync_deja_faite", heure=derniere.strftime("%H:%M")))
            return None

        afficher(t("sync_debut", url=config.URL_CALENDRIER))
        try:
            evenements, source, erreur_api = recuperer_programmation()
        except Exception as exc:
            log.warning("échec de la récupération : %s", exc)
            raise
        if erreur_api:
            log.warning("API indisponible : %s", erreur_api)
            afficher(t("sync_erreur_api", erreur=erreur_api))
        afficher(t("sync_source_" + source, n=len(evenements)))

        maintenant = datetime.now()
        resume = synchroniser(conn, evenements, source, maintenant, simulation=simulation)
    finally:
        conn.close()
    afficher("\n" + formater_resume(resume, maintenant))
    if simulation:
        afficher("\n" + t("sync_simulation"))
    log.info("sync %s : %s", resume["source"],
             {k: len(v) if isinstance(v, list) else v for k, v in resume.items()})
    return resume


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Synchronise la programmation du BLMK.")
    parser.add_argument("--simulation", action="store_true", help="n'enregistre rien")
    parser.add_argument("--si-necessaire", action="store_true",
                        help="ne fait rien si une synchronisation a déjà réussi aujourd'hui")
    args = parser.parse_args(argv)
    configurer_journal()
    try:
        lancer_sync(forcer=not args.si_necessaire, simulation=args.simulation)
    except Exception as exc:  # noqa: BLE001 — message clair pour l'utilisateur
        print(t("sync_erreur_totale", erreur=exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
