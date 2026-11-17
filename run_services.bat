@echo off
REM Lance les 4 microservices + gateway dans des fenetres separees (Windows)
setlocal
set ROOT=%~dp0
start "Bénayfacile — Robot 8001" cmd /c python "%ROOT%services\robot_service.py"
start "Bénayfacile — Engine 8002" cmd /c python "%ROOT%services\engine_service.py"
start "Bénayfacile — DXF 8003" cmd /c python "%ROOT%services\dxf_service.py"
start "Bénayfacile — Rapport 8004" cmd /c python "%ROOT%services\report_service.py"
start "Bénayfacile — Gateway 8090" cmd /c python "%ROOT%gateway\app.py"
echo.
echo Services lances. Tableau de bord : http://127.0.0.1:8090
echo Fermez les fenetres ou lancez stop_services.bat pour arreter.
