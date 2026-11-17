<#
Sauvegarde le projet SOGEN (EGESYS + G++) sur GitHub, en une fois : enregistre les modifications (commit) et les envoie
(push). Sert d'HISTORIQUE (revenir en arrière si une modification casse quelque chose) et de copie de secours.

  sauvegarder.bat                         Demande une courte description, puis sauvegarde
  sauvegarder.bat -Message "texte"        Sauvegarde avec cette description, sans question

Le passage d'un PC à l'autre n'a PAS besoin de GitHub : OneDrive synchronise déjà le dossier du projet (y compris
l'historique Git, dossier caché .git). Sauvegarder depuis un seul PC à la fois, quand OneDrive est à jour.
Ce qui ne part jamais sur GitHub (données clients, journaux, PDF...) est listé dans .gitignore.
Premier lancement : demande l'adresse du dépôt GitHub (ex. https://github.com/compte/sogen.git).
#>
[CmdletBinding()]
param([string]$Message)

# 'Continue' : Git écrit sa progression sur la sortie d'erreur, ce qui ne doit pas arrêter le script.
# Chaque commande est contrôlée par son code de retour ($LASTEXITCODE).
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot

$git = (Get-Command git.exe -ErrorAction SilentlyContinue).Source
if (-not $git -and (Test-Path 'C:\Program Files\Git\cmd\git.exe')) { $git = 'C:\Program Files\Git\cmd\git.exe' }
if (-not $git) { Write-Host 'Git n''est pas installé : lancez installer_poste.bat.' -ForegroundColor Yellow; exit 1 }

function Git { & $git @args; if ($LASTEXITCODE -ne 0) { throw "git $($args -join ' ') a échoué" } }

try {
    # --- Premier lancement : création du dépôt local et lien avec GitHub
    if (-not (Test-Path (Join-Path $PSScriptRoot '.git'))) {
        Write-Host 'Premier lancement : création de l''historique Git du projet.'
        $adresse = Read-Host 'Adresse du dépôt GitHub (ex. https://github.com/compte/sogen.git)'
        if (-not $adresse) { throw 'Adresse vide : rien n''a été fait.' }
        Git init -b main
        Git remote add origin $adresse
    }

    # --- Nom et adresse de l'auteur des sauvegardes (enregistrés dans ce dépôt seulement)
    if (-not (& $git config user.name)) { Git config user.name (Read-Host 'Votre nom (auteur des sauvegardes)') }
    if (-not (& $git config user.email)) { Git config user.email (Read-Host 'Votre adresse mail (celle du compte GitHub)') }

    # --- Enregistrement des modifications
    Git add -A
    $modifs = & $git status --porcelain
    if (-not $modifs) {
        Write-Host 'Aucune modification depuis la dernière sauvegarde.'
    } else {
        Write-Host "Fichiers modifiés :"
        $modifs | ForEach-Object { Write-Host "  $_" }
        if (-not $Message) { $Message = Read-Host 'Description courte de ces modifications (Entrée = automatique)' }
        if (-not $Message) { $Message = "Sauvegarde du $(Get-Date -Format 'dd/MM/yyyy HH:mm')" }
        Git commit -m "$Message (PC $env:COMPUTERNAME)"
    }

    # --- Envoi sur GitHub
    & $git push -u origin main
    if ($LASTEXITCODE -ne 0) {
        # GitHub a des modifications que ce dossier n'a pas (ex. fichier créé sur le site) : on les récupère d'abord
        Write-Host 'GitHub contient des modifications absentes ici : récupération puis nouvel envoi...'
        & $git pull --rebase origin main
        if ($LASTEXITCODE -ne 0) {
            & $git rebase --abort 2>$null
            throw 'Conflit entre GitHub et ce dossier : rien n''a été envoyé. Demandez de l''aide (Claude) avant de continuer.'
        }
        Git push -u origin main
    }
    Write-Host "`nSauvegarde envoyée sur GitHub." -ForegroundColor Green
} catch {
    Write-Host "`nSauvegarde NON terminée : $_" -ForegroundColor Yellow
    exit 1
}
