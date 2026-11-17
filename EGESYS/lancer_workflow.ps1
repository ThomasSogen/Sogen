<#
Workflow EGESYS sous Windows : exécute les ordres déposés par Power Automate dans le OneDrive (workflow\workflow.py).

  lancer_workflow.bat                 Lance le workflow en arrière-plan (une seule instance à la fois)
  lancer_workflow.bat -Identifiants   Enregistre l'identifiant et le mot de passe EGESYS (saisie masquée)
  lancer_workflow.bat -Installer      Lancement automatique à chaque ouverture de session Windows
  lancer_workflow.bat -Desinstaller   Retire le lancement automatique
  lancer_workflow.bat -Etat           Indique si le workflow tourne, sur quel PC (+ dernières lignes du journal)
  lancer_workflow.bat -Arreter        Arrête le workflow (à éviter pendant une exécution : voir processing/)

Journal : %LOCALAPPDATA%\EGESYS\workflow.log  (suivre en direct : Get-Content $env:LOCALAPPDATA\EGESYS\workflow.log -Wait -Tail 20)
Dossier OneDrive : <OneDrive Sogen>\EGESYS, trouvé automatiquement (comme config_egesys.py).
Un seul PC à la fois : <OneDrive>\EGESYS\_poste_actif.json (voir workflow\poste_actif.py).
Les identifiants sont des variables d'environnement de l'utilisateur Windows (EGESYS_IDENTIFIANT, EGESYS_MDP),
jamais écrits dans un fichier du projet.
#>
[CmdletBinding()]  # Une option mal orthographiée provoque une erreur au lieu de lancer le workflow
param([switch]$Identifiants, [switch]$Installer, [switch]$Desinstaller, [switch]$Etat, [switch]$Arreter)

$ErrorActionPreference = 'Stop'
$dossier = $PSScriptRoot
$dossierLocal = Join-Path $env:LOCALAPPDATA 'EGESYS'  # Dossier technique (verrous, travail, journal), voir config_egesys.py
$journal = Join-Path $dossierLocal 'workflow.log'
$raccourci = Join-Path ([Environment]::GetFolderPath('Startup')) 'Workflow EGESYS.lnk'

function Get-DossierOneDrive {
    $force = [Environment]::GetEnvironmentVariable('EGESYS_DRIVE', 'User')
    if ($force) { return $force }
    foreach ($variable in 'OneDriveCommercial', 'OneDrive') {
        $chemin = [Environment]::GetEnvironmentVariable($variable)
        if ($chemin -and (Test-Path $chemin)) { return Join-Path $chemin 'EGESYS' }
    }
    return Join-Path $HOME 'OneDrive - Sogen\EGESYS'
}
$fichierPoste = Join-Path (Get-DossierOneDrive) '_poste_actif.json'

function Get-PosteActif {
    if (-not (Test-Path $fichierPoste)) { return $null }
    try { return Get-Content $fichierPoste -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $null }
}

function Show-PosteActif {
    $poste = Get-PosteActif
    if (-not $poste) { Write-Host 'Aucun PC ne fait tourner le workflow (selon OneDrive).'; return }
    $ici = if ($poste.poste -eq $env:COMPUTERNAME) { ' (ce PC)' } else { ' (AUTRE PC)' }
    Write-Host "PC actif selon OneDrive : $($poste.poste)$ici, depuis le $($poste.depuis), dernier signe de vie le $($poste.battement_lisible)."
}

function Get-Workflow {
    Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
        Where-Object { $_.CommandLine -like '*workflow.py*' }
}

if ($Identifiants) {
    $identifiant = Read-Host 'Identifiant EGESYS'
    $mdpSecurise = Read-Host 'Mot de passe EGESYS' -AsSecureString
    $mdp = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($mdpSecurise))
    [Environment]::SetEnvironmentVariable('EGESYS_IDENTIFIANT', $identifiant, 'User')
    [Environment]::SetEnvironmentVariable('EGESYS_MDP', $mdp, 'User')
    Remove-Variable mdp
    Write-Host 'Identifiants enregistrés (variables utilisateur Windows). Relancez le workflow pour les prendre en compte.'
    return
}

if ($Installer) {
    $shell = New-Object -ComObject WScript.Shell
    $lien = $shell.CreateShortcut($raccourci)
    $lien.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $lien.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $lien.WorkingDirectory = $dossier
    $lien.WindowStyle = 7  # Réduite
    $lien.Description = 'Workflow EGESYS'
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
    $processus = @(Get-Workflow)
    if ($processus.Count -eq 0) { Write-Host "Le workflow n'est pas lancé."; return }
    $processus | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
    # Arrêt brutal : le workflow n'a pas pu libérer sa place, on le fait pour que l'autre PC puisse démarrer tout de suite
    $poste = Get-PosteActif
    if ($poste -and $poste.poste -eq $env:COMPUTERNAME) { Remove-Item $fichierPoste -Confirm:$false -ErrorAction SilentlyContinue }
    Write-Host "Workflow arrêté ($($processus.Count) processus)."
    return
}

if ($Etat) {
    $processus = @(Get-Workflow)
    if ($processus.Count -gt 0) { Write-Host "Workflow en cours sur ce PC (PID $($processus.ProcessId -join ', '))." }
    else { Write-Host "Workflow arrêté sur ce PC." }
    Show-PosteActif
    if (Test-Path $journal) { Write-Host "`n--- Fin de $journal ---"; Get-Content $journal -Tail 15 -Encoding UTF8 }
    return
}

# --- Lancement ---
if (@(Get-Workflow).Count -gt 0) { Write-Host 'Le workflow tourne déjà sur ce PC.'; return }

# Variables EGESYS_* de l'utilisateur : relues dans le registre, pour fonctionner même si elles ont été définies
# après l'ouverture de cette fenêtre.
$variables = [Environment]::GetEnvironmentVariables('User')
foreach ($nom in $variables.Keys) {
    if ($nom -like 'EGESYS_*') { Set-Item -Path "Env:$nom" -Value $variables[$nom] }
}
if (-not $env:EGESYS_IDENTIFIANT -or -not $env:EGESYS_MDP) {
    Write-Host 'Identifiants EGESYS absents : lancez d''abord  lancer_workflow.bat -Identifiants'
    exit 1
}

$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py.exe -ErrorAction SilentlyContinue).Source }
if (-not $python) { Write-Host 'Python introuvable dans le PATH.'; exit 1 }

New-Item -ItemType Directory -Force $dossierLocal | Out-Null
$env:PYTHONUTF8 = '1'  # Journal écrit en UTF-8 (emojis compris)
# cmd /c permet d'AJOUTER au journal (>>) sans l'écraser ; la fenêtre reste cachée.
$commande = "`"`"$python`" -u workflow\workflow.py >> `"$journal`" 2>&1`""
Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" -ArgumentList '/d', '/c', $commande `
    -WorkingDirectory $dossier -WindowStyle Hidden
Start-Sleep -Seconds 3
if (@(Get-Workflow).Count -gt 0) { Write-Host "Workflow lancé en arrière-plan. Journal : $journal" }
else {
    Write-Host "Le workflow n'a pas démarré. Fin du journal ($journal) :"
    if (Test-Path $journal) { Get-Content $journal -Tail 3 -Encoding UTF8 }
    exit 1
}
