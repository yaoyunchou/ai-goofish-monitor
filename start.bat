@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
REM ============================================================
REM  Goofish Monitor - Windows launcher (start.bat)
REM
REM  Usage:
REM    start.bat            Production: install deps -> build UI -> run backend (single port)
REM    start.bat dev        Development: run backend + vite dev server (hot reload)
REM    start.bat build      Build frontend only, do not start anything
REM    start.bat check      Environment check only
REM    start.bat help       Show this help
REM
REM  Notes:
REM    - Production serves everything from http://localhost:8010
REM    - Dev mode runs the frontend on 5173 and proxies API calls to the backend
REM    - Port is read from SERVER_PORT in .env
REM ============================================================

cd /d "%~dp0"

set "MODE=%~1"
if "%MODE%"=="" set "MODE=run"

set "PYTHON_CMD="
set "VENV_PY=.venv\Scripts\python.exe"
set "PYVER=?"

if /i "%MODE%"=="help"   goto :usage
if /i "%MODE%"=="-h"     goto :usage
if /i "%MODE%"=="/?"     goto :usage
if /i "%MODE%"=="start"  set "MODE=run"

echo.
echo ========================================
echo   Goofish Monitor - local launcher
echo ========================================

REM ============================================================
REM [1/5] Environment check
REM ============================================================
echo.
echo [1/5] Checking environment...

set "MISSING="

REM --- Python ---
if exist "%VENV_PY%" (
    set "PYTHON_CMD=%VENV_PY%"
    for /f "tokens=*" %%v in ('"%VENV_PY%" -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PYVER=%%v"
    echo   [OK] Python !PYVER! ^(project venv .venv^)
) else (
    call python --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=python"
        for /f "tokens=*" %%v in ('call python -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PYVER=%%v"
        echo   [OK] Python !PYVER! ^(system interpreter, no .venv found^)
    ) else (
        echo   [X]  Python not found
        set "MISSING=!MISSING! python"
    )
)

REM --- Python >= 3.10 ---
if defined PYTHON_CMD (
    !PYTHON_CMD! -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
    if !errorlevel! neq 0 (
        echo   [X]  Python is too old, need 3.10 or newer
        set "MISSING=!MISSING! python3.10+"
    )
)

REM --- pip ---
if defined PYTHON_CMD (
    !PYTHON_CMD! -m pip --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo   [X]  pip is not available
        set "MISSING=!MISSING! pip"
    )
)

rem --- node ---
call node --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=*" %%v in ('call node --version 2^>nul') do echo   [OK] Node %%v
) else (
    echo   [X]  Node.js not found
    set "MISSING=!MISSING! node"
)

rem --- npm ---
call npm --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=*" %%v in ('call npm --version 2^>nul') do echo   [OK] npm %%v
) else (
    echo   [X]  npm not found
    set "MISSING=!MISSING! npm"
)

REM --- .env ---
if exist ".env" (
    echo   [OK] .env found
) else (
    echo   [WARN] .env missing, copying from .env.example ...
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo   [OK] .env created - fill in DATABASE_URL and your API key before starting
    ) else (
        echo   [X]  .env.example not found either
        set "MISSING=!MISSING! .env"
    )
)

REM --- backend port from .env ---
set "SERVER_PORT=8010"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if /i "%%a"=="SERVER_PORT" (
            for /f "tokens=1 delims= " %%p in ("%%b") do set "SERVER_PORT=%%p"
        )
    )
)

rem --- browser ---
rem Playwright can also drive its own bundled Chromium, so a missing
rem system browser is a warning only, never a hard failure.
set "HAS_BROWSER=0"
set "PW_CHROMIUM=0"

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe"        set "HAS_BROWSER=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"   set "HAS_BROWSER=1"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe"        set "HAS_BROWSER=1"
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"       set "HAS_BROWSER=1"
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"  set "HAS_BROWSER=1"
if exist "%LocalAppData%\Microsoft\Edge\Application\msedge.exe"       set "HAS_BROWSER=1"
if exist "%LocalAppData%\Microsoft\Edge SxS\Application\msedge.exe"   set "HAS_BROWSER=1"

if "!HAS_BROWSER!"=="0" if defined LOCALAPPDATA (
    if exist "!LOCALAPPDATA!\ms-playwright" set "PW_CHROMIUM=1"
)

if "!HAS_BROWSER!"=="1" (
    echo   [OK] Chrome or Edge detected
) else (
    if "!PW_CHROMIUM!"=="1" (
        echo   [OK] Playwright bundled Chromium detected
    ) else (
        echo   [WARN] No Chrome/Edge detected - the scraper needs a browser
        echo        Install one, or run: python -m playwright install chromium
    )
)

if not "!MISSING!"=="" (
    echo.
    echo [X] Missing environment/dependencies:!MISSING!
    echo.
    echo ----------------------------------------
    echo  How to fix on Windows ^(winget^):
    echo ----------------------------------------
    echo   1^) Install Python and Node:
    echo        winget install Python.Python.3.11
    echo        winget install OpenJS.NodeJS.LTS
    echo   2^) Install Playwright:
    echo        python -m pip install playwright
    echo        python -m playwright install chromium
    echo   3^) Install a browser:
    echo        winget install Google.Chrome
    echo   4^) Config files:
    echo        copy .env.example .env
    echo        copy config.json.example config.json
    echo.
    echo Tip: reopen your cmd window after installing so PATH takes effect.
    echo.
    pause
    exit /b 1
)

echo.
echo   [OK] Environment check passed. Backend port: !SERVER_PORT!

if /i "%MODE%"=="check" (
    echo.
    echo Check-only mode, exiting.
    pause
    exit /b 0
)

REM ============================================================
REM [2/5] Python dependencies
REM ============================================================
echo.
echo [2/5] Checking Python dependencies...
if not exist "requirements.txt" (
    echo   [X] requirements.txt not found
    pause
    exit /b 1
)

if not exist "logs" mkdir "logs" >nul 2>&1
set "REQ_STAMP=logs\.deps.stamp"
set "NEED_PIP=1"

if exist "!REQ_STAMP!" (
    for %%f in ("requirements.txt") do set "REQ_TIME=%%~tf"
    set /p "STAMP_TIME="<"!REQ_STAMP!"
    if "!REQ_TIME!"=="!STAMP_TIME!" set "NEED_PIP=0"
)

if "!NEED_PIP!"=="1" (
    echo   Installing Python dependencies ^(first run or requirements.txt changed^) ...
    call !PYTHON_CMD! -m pip install -r requirements.txt --quiet
    if !errorlevel! neq 0 (
        echo   [X] Failed to install Python dependencies
        pause
        exit /b 1
    )
    for %%f in ("requirements.txt") do echo %%~tf>"!REQ_STAMP!"
    echo   [OK] Python dependencies installed
) else (
    echo   [OK] Python dependencies up to date, skipping
)

REM ============================================================
REM [3/5] Frontend dependencies
REM ============================================================
echo.
echo [3/5] Checking frontend dependencies...
if not exist "web-ui" (
    echo   [X] web-ui directory not found
    pause
    exit /b 1
)

pushd web-ui
if not exist "node_modules" (
    echo   First run, installing frontend dependencies ^(this can take a few minutes^) ...
    call npm install
    set "NPM_RC=!errorlevel!"
    if !NPM_RC! neq 0 (
        echo   [X] Failed to install frontend dependencies
        popd
        pause
        exit /b 1
    )
    echo   [OK] Frontend dependencies installed
) else (
    echo   [OK] node_modules present, skipping
)
popd

REM ============================================================
REM Development mode: backend + vite dev server
REM ============================================================
if /i "%MODE%"=="dev" goto :dev_mode

REM ============================================================
REM [4/5] Build frontend
REM ============================================================
echo.
echo [4/5] Building frontend...

if /i "%MODE%"=="build" goto :do_build

set "NEED_BUILD=1"
if exist "dist\index.html" (
    set "NEED_BUILD=0"
    for /f "delims=" %%f in ('dir /b /s /a-d "web-ui\src" 2^>nul') do (
        if "!NEED_BUILD!"=="0" (
            for %%d in ("dist\index.html") do (
                if "%%~tf" LSS "%%~tf" set "NEED_BUILD=1"
            )
        )
    )
)

if "!NEED_BUILD!"=="0" (
    echo   [OK] dist is up to date, skipping build ^(force with: start.bat build^)
    goto :after_build
)

:do_build
echo   Building ...
pushd web-ui
call npm run build
set "BUILD_RC=!errorlevel!"
popd
if !BUILD_RC! neq 0 (
    echo   [X] Frontend build failed
    pause
    exit /b 1
)
if not exist "dist\index.html" (
    echo   [X] Build finished but dist\index.html is missing
    pause
    exit /b 1
)
echo   [OK] Frontend built into dist\

if /i "%MODE%"=="build" (
    echo.
    echo Build-only mode, exiting.
    pause
    exit /b 0
)

:after_build

REM ============================================================
REM [5/5] Start backend
REM ============================================================
echo.
echo [5/5] Starting backend ...
echo ========================================
echo   App:     http://localhost:!SERVER_PORT!
echo   API doc: http://localhost:!SERVER_PORT!/docs
echo   Login:   admin / admin123
echo ========================================
echo.
echo Press Ctrl+C to stop.
echo.

!PYTHON_CMD! -m src.app
goto :eof

REM ============================================================
REM Development mode branch
REM ============================================================
:dev_mode
echo.
echo [4/4] Starting dev servers ^(backend + vite hot reload^) ...
echo ========================================
echo   Frontend: http://localhost:5173   ^(hot reload^)
echo   Backend:  http://127.0.0.1:!SERVER_PORT!
echo   Login:    admin / admin123
echo ========================================
echo.
echo Close the two spawned windows to stop the servers.
echo.

start "goofish-backend" cmd /k "!PYTHON_CMD! -m src.app"
timeout /t 2 /nobreak >nul
start "goofish-frontend" cmd /k "cd web-ui && set BACKEND_PORT=!SERVER_PORT!&& npm run dev"

echo Both services launched in separate windows.
goto :eof

REM ============================================================
:usage
echo.
echo Goofish Monitor - Windows launcher
echo.
echo Usage: start.bat [mode]
echo.
echo   Modes:
echo     ^(none^)   Production: install deps, build UI, run backend ^(single port^)
echo     dev      Development: backend + vite dev server ^(hot reload^)
echo     build    Build frontend only
echo     check    Environment check only, then exit
echo     help     Show this help
echo.
echo Port: read from SERVER_PORT in .env
echo.
goto :eof
