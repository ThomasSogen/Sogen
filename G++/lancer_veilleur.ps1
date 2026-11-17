<#
Veilleur GENICIA++ sous Windows : exécute les demandes déposées par Power Automate dans le OneDrive
(veilleur\veilleur_genicia.py).

  lancer_veilleur.bat                 Lance le veilleur en arrière-plan (une seule instance à la fois)
  lancer_veilleur.bat -Identifiants   Enregistre l'identifiant et le mot de passe GENICIA++ (saisie masquée)
  lancer_veilleur.bat -Installer      Lancement automatique à chaque ouverture de session Windows
  lancer_veilleur.bat -Desinstaller   Retire le lancement automatique
  lancer_veilleur.bat -Etat           Indique si le veilleur tourne, sur quel PC (+ dernières lignes du journal)
  lancer_veilleur.bat -Arreter        Arrête le veilleur (refusé si un traitement est en cours)

Journal (propre à chaque PC) : %LOCALAPPDATA%\GENICIA\veilleur.log
  suivre en direct : Get-Content $env:LOCALAPPDATA\GENICIA\veilleur.log -Wait -Tail 20 -Encoding UTF8
Dossier OneDrive : <OneDrive Sogen>\G++, trouvé automatiquement (comme config_genicia.py).
Un seul PC à la fois : <OneDrive>\G++\_poste_actif.json (voir veilleur\poste_actif.py).
Les identifiants GENICIA++ sont dans le Gestionnaire d'identifiants Windows, jamais dans un fichier.
#>
[CmdletBinding()]
param([switch]$Identifiants, [switch]$Installer, [switch]$Desinstaller, [switch]$Etat, [switch]$Arreter)

$ErrorActionPreference = 'Stop'
$dossier = $PSScriptRoot
$dossierLocal = Join-Path $env:LOCALAPPDATA 'GENICIA'   # journal, verrou, travail : propres à ce PC (config_genicia.py)
$journal = Join-Path $dossierLocal 'veilleur.log'
$raccourci = Join-Path ([Environment]::GetFolderPath('Startup')) 'Veilleur GENICIA++.lnk'

function Get-DossierOneDrive {
    $force = [Environment]::GetEnvironmentVariable('GENICIA_DRIVE', 'User')
    if ($force) { return $force }
    foreach ($variable in 'OneDriveCommercial', 'OneDrive') {
        $chemin = [Environment]::GetEnvironmentVariable($variable)
        if ($chemin -and (Test-Path $chemin)) { return Join-Path $chemin 'G++' }
    }
    return Join-Path $HOME 'OneDrive - Sogen\G++'
}
$drive = Get-DossierOneDrive
$fichierPoste = Join-Path $drive '_poste_actif.json'

function Get-PosteActif {
    if (-not (Test-Path $fichierPoste)) { return $null }
    try { return Get-Content $fichierPoste -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $null }
}

function Show-PosteActif {
    $poste = Get-PosteActif
    if (-not $poste) { Write-Host 'Aucun PC ne fait tourner le veilleur (selon OneDrive).'; return }
    $ici = if ($poste.poste -eq $env:COMPUTERNAME) { ' (ce PC)' } else { ' (AUTRE PC)' }
    Write-Host "PC actif selon OneDrive : $($poste.poste)$ici, depuis le $($poste.depuis), dernier signe de vie le $($poste.battement_lisible)."
}

function Get-Veilleur {
    Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
        Where-Object { $_.CommandLine -like '*veilleur_genicia.py*' }
}

function Get-Python {
    $python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $python) { $python = (Get-Command py.exe -ErrorAction SilentlyContinue).Source }
    if (-not $python) { Write-Host 'Python introuvable dans le PATH.'; exit 1 }
    return $python
}

if ($Identifiants) {
    & (Get-Python) (Join-Path $dossier 'enregistrer_identifiants.py')
    return
}

if ($Installer) {
    $shell = New-Object -ComObject WScript.Shell
    $lien = $shell.CreateShortcut($raccourci)
    $lien.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $lien.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $lien.WorkingDirectory = $dossier
    $lien.WindowStyle = 7
    $lien.Description = 'Veilleur GENICIA++'
    $lien.Save()
    Write-Host "Lancement automatique installé : $raccourci"
    return
}

if ($Desinstaller) {
    if (Test-Path $raccourci) { Remove-Item $raccourci -Confirm:$false; Write-Host 'Lancement automatique retiré.' }
    else { Write-Host 'Aucun lancement automatique installé.' }
    return
}

if ($Arreter) {
    $processus = @(Get-Veilleur)
    if ($processus.Count -eq 0) { Write-Host "Le veilleur n'est pas lancé."; return }
    $enCours = @(Get-ChildItem (Join-Path $drive 'processing') -Filter *.json -ErrorAction SilentlyContinue)
    if ($enCours.Count -gt 0) {
        Write-Host "Un traitement est en cours ($($enCours.Name -join ', ')) : attendez qu'il se termine puis relancez -Arreter."
        exit 1
    }
    $processus | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
    # Arrêt brutal : le veilleur n'a pas pu libérer sa place, on le fait pour que l'autre PC puisse démarrer tout de suite
    $poste = Get-PosteActif
    if ($poste -and $poste.poste -eq $env:COMPUTERNAME) { Remove-Item $fichierPoste -Confirm:$false -ErrorAction SilentlyContinue }
    Write-Host "Veilleur arrêté ($($processus.Count) processus)."
    return
}

if ($Etat) {
    $processus = @(Get-Veilleur)
    if ($processus.Count -gt 0) { Write-Host "Veilleur en cours sur ce PC (PID $($processus.ProcessId -join ', '))." }
    else { Write-Host 'Veilleur arrêté sur ce PC.' }
    Show-PosteActif
    if (Test-Path $journal) { Write-Host "`n--- Fin de $journal ---"; Get-Content $journal -Tail 15 -Encoding UTF8 }
    return
}

# --- Lancement ---
if (@(Get-Veilleur).Count -gt 0) { Write-Host 'Le veilleur tourne déjà sur ce PC.'; return }
$python = Get-Python
New-Item -ItemType Directory -Force $dossierLocal | Out-Null
$env:PYTHONUTF8 = '1'
# cmd /c permet d'AJOUTER au journal (>>) sans l'écraser ; la fenêtre reste cachée.
$commande = "`"`"$python`" -u veilleur\veilleur_genicia.py >> `"$journal`" 2>&1`""
Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" -ArgumentList '/d', '/c', $commande `
    -WorkingDirectory $dossier -WindowStyle Hidden
Start-Sleep -Seconds 3
if (@(Get-Veilleur).Count -gt 0) { Write-Host "Veilleur lancé en arrière-plan. Journal : $journal" }
else {
    Write-Host "Le veilleur n'a pas démarré. Fin du journal ($journal) :"
    if (Test-Path $journal) { Get-Content $journal -Tail 3 -Encoding UTF8 }
    exit 1
}
