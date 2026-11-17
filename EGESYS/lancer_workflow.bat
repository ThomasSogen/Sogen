@echo off
rem Workflow EGESYS (Windows). Double-clic = lancement en arriere-plan.
rem Options : -Identifiants  -Installer  -Desinstaller  -Etat  -Arreter   (voir lancer_workflow.ps1)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0lancer_workflow.ps1" %*
if "%~1"=="" pause
