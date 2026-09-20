@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
REM ============================================================
REM  Local dev launcher: backend + frontend
REM  Usage: run dev_start.bat (or double-click it)
REM
REM  Ports:
REM    - backend port comes from SERVER_PORT in .env (default 8000)
REM    - frontend runs on 5173; BACKEND_PORT tells vite where to proxy
REM
REM  Note: this script only starts services. It does NOT install
REM  dependencies or build the frontend. Use start.bat for that.
REM ============================================================
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "PYTHON_CMD="

REM ---------- Resolve Python: prefer project venv, else system ----------
if exist "%VENV_PY%" (
    set "PYTHON_CMD=%VENV_PY%"
    echo Python: project venv ^(.venv^)
) else (
    call python --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=python"
        echo Python: system interpreter ^(no .venv found^)
    ) else (
        echo.
        echo [X] Python not found.
        echo     Create a venv:
        echo         python -m venv .venv
        echo         .venv\Scripts\python.exe -m pip install -r requirements.txt
        echo     Or install Python and make sure it is on PATH.
        echo.
        pause
        exit /b 1
    )
)

if not exist logs mkdir logs >nul 2>&1

REM ---------- Read SERVER_PORT from .env ----------
set "BACKEND_PORT=8000"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if /i "%%a"=="SERVER_PORT" (
            for /f "tokens=1 delims= " %%p in ("%%b") do set "BACKEND_PORT=%%p"
        )
    )
)

REM ---------- Sanity check the app entry point ----------
if not exist "src\app.py" (
    echo.
    echo [X] src\app.py not found. Run this script from the project root.
    echo.
    pause
    exit /b 1
)

if not exist "web-ui\node_modules" (
    echo.
    echo [WARN] web-ui\node_modules not found.
    echo        The frontend may fail to start. Run: cd web-ui ^&^& npm install
    echo.
)

echo.
echo ========================================
echo   Goofish Monitor - dev launcher
echo ========================================
echo   Backend  : http://127.0.0.1:!BACKEND_PORT!
echo   Frontend : http://localhost:5173
echo   Login    : admin / admin123
echo ========================================
echo.

echo [1/2] Starting backend ...
start "goofish-backend" cmd /k "!PYTHON_CMD! -m src.app"

timeout /t 2 /nobreak >nul

echo [2/2] Starting frontend ^(proxy -^> 127.0.0.1:!BACKEND_PORT!^) ...
start "goofish-frontend" cmd /k "cd web-ui && set BACKEND_PORT=!BACKEND_PORT!&& npm run dev"

echo.
echo Both services launched in separate windows.
echo Close those two windows to stop the servers.
echo.
endlocal
