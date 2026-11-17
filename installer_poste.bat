@echo off
rem Prepare ou verifie ce PC pour les projets EGESYS et G++ (double-clic). Option : -Verifier (ne modifie rien)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer_poste.ps1" %*
pause
