@echo off
REM ===================================================================
REM  Bénayfacile — construit l'application de bureau et son installateur
REM    1. dépendances   2. tests   3. application (dist\Benayfacile\)
REM    4. installateur  (installer\Benayfacile-Setup-x.y.z.exe)
REM ===================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo [1/4] Dependances...
python -m pip install -r requirements.txt pyinstaller pywin32 pytest httpx || goto :err

echo [2/4] Tests du moteur (le build s'arrete si un test echoue)...
python -m pytest tests -q || goto :err

echo [3/4] Application (PyInstaller)...
python -m PyInstaller --noconfirm --clean Benayfacile.spec || goto :err

echo [4/4] Installateur (Inno Setup)...
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
    if exist %%P set "ISCC=%%~P"
)
if not defined ISCC (
    echo Inno Setup 6 n'est pas installe : il sert uniquement a fabriquer l'installateur.
    choice /C ON /M "L'installer maintenant avec winget (gratuit, ~5 Mo) ?"
    if errorlevel 2 goto :sans_installateur
    winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
    for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
        if exist %%P set "ISCC=%%~P"
    )
)
if not defined ISCC goto :sans_installateur
"%ISCC%" installer.iss || goto :err
echo.
echo OK : installateur pret dans %~dp0installer\
echo      Donnez ce Setup.exe aux utilisateurs : installation, menu Demarrer, icone Bureau.
exit /b 0

:sans_installateur
echo.
echo OK (sans installateur) : %~dp0dist\Benayfacile\Benayfacile.exe
echo Relancez build_exe.bat apres avoir installe Inno Setup 6 pour obtenir le Setup.exe.
exit /b 0

:err
echo.
echo ECHEC DU BUILD (code %errorlevel%)
pause
exit /b 1
