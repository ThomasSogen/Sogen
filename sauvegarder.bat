@echo off
rem Sauvegarde le projet sur GitHub (double-clic). Option : -Message "description"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sauvegarder.ps1" %*
pause
