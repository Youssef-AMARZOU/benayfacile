@echo off
REM Construit dist\Benayfacile.exe (un seul fichier, Windows x64)
setlocal
cd /d "%~dp0"
echo [1/3] Dependances...
python -m pip install -r requirements.txt pyinstaller pywin32 pytest httpx2 || goto :err
echo [2/3] Tests du moteur (le build s'arrete si un test echoue)...
python -m pytest tests -q || goto :err
echo [3/3] PyInstaller...
python -m PyInstaller --noconfirm --clean Benayfacile.spec || goto :err
echo.
echo OK : %~dp0dist\Benayfacile.exe
echo Au premier lancement, le dossier Benayfacile_donnees\ est cree a cote de l'exe.
exit /b 0
:err
echo.
echo ECHEC DU BUILD (code %errorlevel%)
exit /b 1
