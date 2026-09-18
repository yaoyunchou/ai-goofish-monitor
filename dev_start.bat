@echo off
REM ============================================================
REM  Local dev launcher: backend + frontend
REM  Usage: run dev_start.bat (or double-click it)
REM
REM  Ports:
REM    - backend port comes from SERVER_PORT in .env (default 8000,
REM      this worktree uses 8001 because 8000 is already taken)
REM    - frontend runs on 5173; BACKEND_PORT tells vite where to proxy
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist logs mkdir logs

REM Read SERVER_PORT from .env, use it as the vite proxy target
set BACKEND_PORT=8001
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if /i "%%a"=="SERVER_PORT" set BACKEND_PORT=%%b
)

echo Backend port: %BACKEND_PORT%

echo [1/2] Starting backend ...
start "goofish-backend" cmd /k ".venv\Scripts\python.exe -m src.app"

echo [2/2] Starting frontend (proxy -^> 127.0.0.1:%BACKEND_PORT%) ...
start "goofish-frontend" cmd /k "cd web-ui && set BACKEND_PORT=%BACKEND_PORT%&& npm run dev"

echo.
echo   Frontend: http://localhost:5173
echo   Backend : http://127.0.0.1:%BACKEND_PORT%
echo   Login   : admin / admin123
echo.
echo Close the two spawned windows to stop the servers.
echo.
endlocal
