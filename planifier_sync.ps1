# Crée (ou remplace) une tâche planifiée Windows qui synchronise
# la programmation du BLMK chaque jour.
#
# À lancer une seule fois, dans PowerShell, depuis ce dossier :
#     powershell -ExecutionPolicy Bypass -File .\planifier_sync.ps1
# Options :
#     -Heure "07:30"      heure de la synchronisation quotidienne (défaut 07:00)
#     -Supprimer          supprime la tâche au lieu de la créer
#
# La tâche tourne sous votre compte, uniquement quand vous êtes connecté
# (aucun mot de passe demandé). Si le PC était éteint à l'heure prévue,
# elle se lance dès que possible. Le résultat est écrit dans data\sync.log.

param(
    [string]$Heure = "07:00",
    [switch]$Supprimer
)

$ErrorActionPreference = "Stop"
$NomTache = "Musee Zoune - synchronisation programmation BLMK"
$Dossier = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Dossier ".venv\Scripts\pythonw.exe"   # pythonw : pas de fenêtre noire

if ($Supprimer) {
    Unregister-ScheduledTask -TaskName $NomTache -Confirm:$false
    Write-Host "Tâche « $NomTache » supprimée."
    exit 0
}

if (-not (Test-Path $Python)) {
    throw "Python du projet introuvable ($Python). Créez d'abord l'environnement : py -m venv .venv puis .venv\Scripts\pip install -r requirements.txt"
}

$Action = New-ScheduledTaskAction -Execute $Python -Argument "-m musee_zoune.sync" -WorkingDirectory $Dossier
$Declencheur = New-ScheduledTaskTrigger -Daily -At $Heure
$Reglages = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
$Utilisateur = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $NomTache -Action $Action -Trigger $Declencheur `
    -Settings $Reglages -Principal $Utilisateur `
    -Description "Récupère la programmation de blmk.de/kalender et enregistre les changements (Musée Zoune)." `
    -Force | Out-Null

Write-Host "Tâche « $NomTache » créée : tous les jours à $Heure."
Write-Host "Pour la tester tout de suite : Start-ScheduledTask -TaskName '$NomTache'"
