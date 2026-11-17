@echo off
rem Nettoyage du OneDrive EGESYS (completed, error, result, result\pdf). Double-clic = supprime tout (pas de question).
rem Options possibles : --simulation   --jours 30   (voir nettoyer_onedrive.py)
cd /d "%~dp0"
set PYTHONUTF8=1
python nettoyer_onedrive.py %*
echo.
pause
