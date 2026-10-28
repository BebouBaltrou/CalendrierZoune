@echo off
rem Lance Musee Zoune (double-clic).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Premiere installation, patientez quelques minutes...
    py -m venv .venv || goto erreur
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto erreur
)
start "" ".venv\Scripts\pythonw.exe" -m musee_zoune.app
exit /b 0

:erreur
echo Installation impossible. Verifiez que Python 3 est installe (commande py).
pause
exit /b 1
