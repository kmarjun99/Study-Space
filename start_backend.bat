@echo off
SETLOCAL EnableDelayedExpansion

cd /d "%~dp0"

echo ==========================================
echo StudySpace Manager - One-Click Launcher
echo ==========================================

IF NOT EXIST "backend" (
    echo [ERROR] Could not find 'backend' folder!
    echo Please make sure you are in the SSPACE folder.
    pause
    exit /b 1
)

cd backend

:: Check for existing run script in backend and use it if possible, or just copy the logic here
IF EXIST "run_backend.bat" (
    call run_backend.bat
) ELSE (
    echo [ERROR] run_backend.bat not found in backend folder!
    pause
)
