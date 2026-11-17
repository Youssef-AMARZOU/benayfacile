@echo off
REM Arrete les processus Bénayfacile ecoutant sur 8001-8004 et 8090
for %%p in (8001 8002 8003 8004 8090) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p " ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
  )
)
echo Services Bénayfacile arretes.
