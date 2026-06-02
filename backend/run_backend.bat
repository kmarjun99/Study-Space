@echo off
SETLOCAL EnableDelayedExpansion

cd /d "%~dp0"

echo ==========================================
echo StudySpace Manager Backend Setup & Run
echo ==========================================

SET LOGFILE=backend_setup.log
echo [INFO] Starting setup at %TIME% > %LOGFILE%

:: Priority 1: Check for Python 3.12 via Launcher (Stable)
py -3.12 --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo [INFO] Found Python 3.12 via launcher.
    echo [INFO] Found Python 3.12 via launcher. >> %LOGFILE%
    SET PYTHON_CMD=py -3.12
    GOTO :FOUND_PYTHON
)

:: Priority 2: Check for Python 3.11 via Launcher (Stable)
py -3.11 --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo [INFO] Found Python 3.11 via launcher.
    echo [INFO] Found Python 3.11 via launcher. >> %LOGFILE%
    SET PYTHON_CMD=py -3.11
    GOTO :FOUND_PYTHON
)

:: Priority 3: Fallback to whatever 'python' is on PATH (Check version?)
python --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo [INFO] Found default 'python' command.
    echo [INFO] Found default 'python' command. >> %LOGFILE%
    SET PYTHON_CMD=python
) ELSE (
    echo [ERROR] No compatible Python found.
    echo [ERROR] No compatible Python found. >> %LOGFILE%
    echo Please install Python 3.12.
    pause
    exit /b 1
)

:FOUND_PYTHON
echo Using command: !PYTHON_CMD!
echo Using command: !PYTHON_CMD! >> %LOGFILE%

:: Destroy old venv if it exists (to prevent version mismatch)
:: Create Venv if not exists
IF NOT EXIST "venv" (
    echo [INFO] Creating virtual environment...
    echo [INFO] Creating virtual environment... >> %LOGFILE%
    !PYTHON_CMD! -m venv venv >> %LOGFILE% 2>&1
    IF !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Failed to create venv. See %LOGFILE%.
        echo [ERROR] Failed to create venv. >> %LOGFILE%
        pause
        exit /b 1
    )
) ELSE (
    echo [INFO] Venv exists. Skipping creation.
)

:: Activate Venv
call venv\Scripts\activate.bat >> %LOGFILE% 2>&1

:: Install Requirements
echo [INFO] Installing dependencies...
echo [INFO] Installing dependencies... >> %LOGFILE%
pip install -r requirements.txt >> %LOGFILE% 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies. See %LOGFILE%.
    echo [ERROR] Failed to install dependencies. >> %LOGFILE%
    type %LOGFILE%
    pause
    exit /b 1
)

:: Run Seed (Only if DB doesn't exist to preserve data)
IF NOT EXIST "study_space.db" (
    echo [INFO] Database not found. Seeding...
    echo [INFO] Database not found. Seeding... >> %LOGFILE%
    python seed.py >> %LOGFILE% 2>&1
    IF !ERRORLEVEL! NEQ 0 (
        echo [WARNING] Seed script failed. See %LOGFILE%.
    )
) ELSE (
    echo [INFO] Database exists. Skipping seed to preserve data.
    echo [INFO] Database exists. Skipping seed to preserve data. >> %LOGFILE%
)

:: Start Server
echo [INFO] Starting Uvicorn Server...
echo [INFO] Starting Uvicorn Server... >> %LOGFILE%
echo ==========================================
echo Server running at: http://localhost:8000
echo Documentation at:  http://localhost:8000/docs
echo ==========================================

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
