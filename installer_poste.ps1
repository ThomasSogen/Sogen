<#
Prépare ou vérifie un PC pour faire tourner les projets EGESYS et G++ (à lancer une fois par PC, puis en cas de doute).

  installer_poste.bat              Vérifie tout et propose de corriger ce qui manque (une question par correction)
  installer_poste.bat -Verifier    Vérifie seulement, sans rien modifier ni rien demander

Le code du projet est synchronisé par OneDrive : il est identique sur tous les PC. Ce script s'occupe de ce qui NE se
synchronise PAS : Python et ses bibliothèques, identifiants (EGESYS, GENICIA++), Java Access Bridge, Git, démarrage
automatique. Il n'affiche jamais un identifiant ni un mot de passe.
#>
[CmdletBinding()]
param([switch]$Verifier)

$ErrorActionPreference = 'Stop'
$racine = $PSScriptRoot
$egesys = Join-Path $racine 'EGESYS'
$gpp = Join-Path $racine 'G++'
$script:problemes = 0

function Ok($texte)        { Write-Host "  [OK] $texte" -ForegroundColor Green }
function Info($texte)      { Write-Host "  [i]  $texte" -ForegroundColor Gray }
function Probleme($texte)  { Write-Host "  [!!] $texte" -ForegroundColor Yellow; $script:problemes++ }
function Titre($texte)     { Write-Host "`n$texte" -ForegroundColor Cyan }
function Corriger($question) {
    if ($Verifier) { return $false }
    return (Read-Host "       $question (O/N)") -match '^[oOyY]'
}

Write-Host "Vérification du PC $env:COMPUTERNAME pour les projets SOGEN" -ForegroundColor Cyan
if ($Verifier) { Write-Host '(mode vérification : rien ne sera modifié)' }

# ------------------------------------------------------------------------------------------------ Python
Titre '1. Python 3.12 64 bits'
function Get-Python {
    foreach ($nom in 'python.exe', 'py.exe') {
        $commande = Get-Command $nom -ErrorAction SilentlyContinue
        if ($commande -and $commande.Source -notlike '*\WindowsApps\*') { return $commande.Source }
    }
    return $null
}
$python = Get-Python
if (-not $python) {
    Probleme "Python introuvable (le « python » du Microsoft Store ne compte pas)."
    if (Corriger 'Installer Python 3.12 avec winget ?') {
        winget install --id Python.Python.3.12 -e --scope user
        Info 'Fermez puis rouvrez cette fenêtre, et relancez installer_poste.bat.'
        exit 1
    }
} else {
    $version = & $python -c "import sys, struct; print(f'{sys.version_info[0]}.{sys.version_info[1]} {struct.calcsize(chr(80)) * 8}')"
    if ($version -match '^3\.(1[2-9]) 64$') { Ok "Python $version bits ($python)" }
    else { Probleme "Python $version bits trouvé ($python) : il faut Python 3.12 (ou plus) 64 bits." }
}

# ------------------------------------------------------------------------------------------------ Bibliothèques
Titre '2. Bibliothèques Python'
# nom à importer = nom du paquet à installer
$bibliotheques = [ordered]@{
    'requests' = 'requests'; 'bs4' = 'beautifulsoup4'; 'openpyxl' = 'openpyxl'; 'pypdf' = 'pypdf'   # EGESYS (+ G++ : pypdf)
    'pywinauto' = 'pywinauto'; 'pyjab' = 'pyjab'; 'keyring' = 'keyring'; 'pyodbc' = 'pyodbc'      # G++
}
if ($python) {
    # Un seul appel, sans message d'erreur (PowerShell 5.1 traite la sortie d'erreur de Python comme une erreur fatale)
    $modules = ($bibliotheques.Keys | ForEach-Object { "'$_'" }) -join ','
    $absents = & $python -c "import importlib.util as u; print(' '.join(m for m in [$modules] if u.find_spec(m) is None))"
    $manquants = @($absents -split ' ' | Where-Object { $_ } | ForEach-Object { $bibliotheques[$_] })
    if ($manquants.Count -eq 0) { Ok "Toutes présentes ($($bibliotheques.Values -join ', '))" }
    else {
        Probleme "Manquantes : $($manquants -join ', ')"
        if (Corriger 'Les installer maintenant ?') {
            & $python -m pip install @manquants
            if ($LASTEXITCODE -eq 0) { Ok 'Installées.' ; $script:problemes-- } else { Probleme 'Échec de pip install (voir ci-dessus).' }
        }
    }
} else { Info 'Python absent : vérification sautée.' }

# ------------------------------------------------------------------------------------------------ OneDrive
Titre '3. Dossiers OneDrive'
$onedrive = $null
foreach ($variable in 'OneDriveCommercial', 'OneDrive') {
    $chemin = [Environment]::GetEnvironmentVariable($variable)
    if ($chemin -and (Test-Path $chemin)) { $onedrive = $chemin; break }
}
if (-not $onedrive) { Probleme 'OneDrive Sogen introuvable sur ce PC : installez et connectez OneDrive.' }
else {
    Ok "OneDrive : $onedrive"
    foreach ($sous in 'EGESYS', 'G++') {
        $d = Join-Path $onedrive $sous
        if (Test-Path $d) { Ok "Dossier $sous trouvé ($d)" } else { Probleme "Dossier $d absent (pas encore synchronisé ?)" }
    }
}
foreach ($ancienne in 'EGESYS_DRIVE', 'GENICIA_DRIVE') {
    $valeur = [Environment]::GetEnvironmentVariable($ancienne, 'User')
    if ($valeur) {
        Probleme "Ancienne variable $ancienne = $valeur : inutile maintenant (dossier trouvé automatiquement) et propre à un PC."
        if (Corriger "Supprimer la variable $ancienne ?") {
            [Environment]::SetEnvironmentVariable($ancienne, $null, 'User'); Ok "$ancienne supprimée."; $script:problemes--
        }
    }
}

# ------------------------------------------------------------------------------------------------ EGESYS
Titre '4. EGESYS : identifiants'
$id = [Environment]::GetEnvironmentVariable('EGESYS_IDENTIFIANT', 'User')
$mdp = [Environment]::GetEnvironmentVariable('EGESYS_MDP', 'User')
if ($id -and $mdp) { Ok 'Identifiants EGESYS enregistrés.' }
else {
    Probleme 'Identifiants EGESYS absents.'
    if (Corriger 'Les saisir maintenant ?') {
        & (Join-Path $egesys 'lancer_workflow.ps1') -Identifiants; $script:problemes--
    }
}
Remove-Variable id, mdp

# ------------------------------------------------------------------------------------------------ GENICIA++
Titre '5. GENICIA++ : logiciel, Java Access Bridge, identifiants'
if (Test-Path 'C:\Logicia\Genicia\GPP\packages\genicia.exe') { Ok 'GENICIA++ installé (C:\Logicia\Genicia\GPP).' }
else { Probleme 'GENICIA++ absent de C:\Logicia\Genicia\GPP : le veilleur G++ ne pourra pas tourner sur ce PC.' }
$jabswitch = 'C:\Program Files\Java\jre1.8.0_25\bin\jabswitch.exe'
if (-not (Test-Path $jabswitch)) { Probleme "Java 8u25 64 bits absent ($jabswitch)." }
else {
    $proprietes = Join-Path $HOME '.accessibility.properties'
    $actif = (Test-Path $proprietes) -and (Select-String -Path $proprietes -Pattern '^\s*assistive_technologies=.*AccessBridge' -Quiet)
    if ($actif) { Ok 'Java Access Bridge activé.' }
    else {
        Probleme 'Java Access Bridge désactivé (Python ne verrait pas les fenêtres de GENICIA++).'
        if (Corriger 'L''activer maintenant ?') {
            & $jabswitch -enable; Ok 'Activé. Fermez et rouvrez GENICIA++ s''il est ouvert.'; $script:problemes--
        }
    }
}
if ($python) {
    # Renvoie seulement OUI/NON : les identifiants ne sont jamais affichés
    $present = & $python -c "import keyring; i = keyring.get_password('GENICIA++', 'identifiant'); print('OUI' if i and keyring.get_password('GENICIA++', i) else 'NON')"
    if ($present -eq 'OUI') { Ok 'Identifiants GENICIA++ enregistrés.' }
    else {
        Probleme 'Identifiants GENICIA++ absents.'
        if (Corriger 'Les saisir maintenant ?') {
            & $python (Join-Path $gpp 'enregistrer_identifiants.py'); $script:problemes--
        }
    }
}

# ------------------------------------------------------------------------------------------------ Git
Titre '6. Git (sauvegarde sur GitHub)'
$git = Get-Command git.exe -ErrorAction SilentlyContinue
if (-not $git -and (Test-Path 'C:\Program Files\Git\cmd\git.exe')) { $git = 'C:\Program Files\Git\cmd\git.exe' }
if ($git) { Ok "Git installé." }
else {
    Probleme 'Git absent : sauvegarder.bat ne pourra pas envoyer le projet sur GitHub.'
    if (Corriger 'Installer Git avec winget ?') {
        winget install --id Git.Git -e
        Info 'Fermez puis rouvrez les fenêtres PowerShell et VS Code pour que Git soit reconnu.'
    }
}

# ------------------------------------------------------------------------------------------------ Démarrage auto
Titre '7. Démarrage automatique à l''ouverture de session'
Info 'Possible sur les deux PC : le verrou OneDrive empêche que les deux traitent les mails en même temps.'
$demarrage = [Environment]::GetFolderPath('Startup')
foreach ($programme in @(
        @{ Nom = 'Workflow EGESYS'; Lien = 'Workflow EGESYS.lnk'; Script = Join-Path $egesys 'lancer_workflow.ps1' },
        @{ Nom = 'Veilleur GENICIA++'; Lien = 'Veilleur GENICIA++.lnk'; Script = Join-Path $gpp 'lancer_veilleur.ps1' })) {
    $lien = Join-Path $demarrage $programme.Lien
    if (Test-Path $lien) {
        $cible = (New-Object -ComObject WScript.Shell).CreateShortcut($lien).Arguments
        if ($cible -like "*$($programme.Script)*") { Ok "$($programme.Nom) : démarrage automatique installé." }
        else {
            Probleme "$($programme.Nom) : le raccourci de démarrage pointe vers un autre emplacement du projet."
            if (Corriger 'Le refaire vers ce dossier ?') { & $programme.Script -Installer; $script:problemes-- }
        }
    } else {
        Info "$($programme.Nom) : pas de démarrage automatique sur ce PC."
        if (Corriger "Installer le démarrage automatique du $($programme.Nom) ?") { & $programme.Script -Installer }
    }
}

# ------------------------------------------------------------------------------------------------ PC actif
Titre '8. Quel PC traite les mails en ce moment ?'
if ($onedrive) {
    foreach ($sous in 'EGESYS', 'G++') {
        $fichier = Join-Path $onedrive "$sous\_poste_actif.json"
        if (Test-Path $fichier) {
            $poste = Get-Content $fichier -Raw -Encoding UTF8 | ConvertFrom-Json
            $ici = if ($poste.poste -eq $env:COMPUTERNAME) { 'ce PC' } else { 'AUTRE PC' }
            Info "$sous : $($poste.poste) ($ici), dernier signe de vie le $($poste.battement_lisible)."
        } else { Info "$sous : aucun PC actif." }
    }
}

Write-Host ''
if ($script:problemes -le 0) { Write-Host 'Tout est prêt sur ce PC.' -ForegroundColor Green }
else { Write-Host "$($script:problemes) point(s) à corriger (voir [!!] ci-dessus)." -ForegroundColor Yellow }
