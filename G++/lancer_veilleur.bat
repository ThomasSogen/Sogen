@echo off
rem Veilleur GENICIA++ (Windows). Double-clic = lancement en arriere-plan.
rem Options : -Identifiants  -Installer  -Desinstaller  -Etat  -Arreter   (voir lancer_veilleur.ps1)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0lancer_veilleur.ps1" %*
if "%~1"=="" pause
