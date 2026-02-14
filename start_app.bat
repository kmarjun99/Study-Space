@echo off
SETLOCAL EnableDelayedExpansion

cd /d "%~dp0"

echo ==========================================
echo StudySpace Manager - Full Stack Launcher
echo ==========================================

:: 1. Start Backend in a new window
echo [INFO] Starting Backend Server...
start "StudySpace Backend" cmd /k "call backend\run_backend.bat"

:: 2. Wait a few seconds for backend to initialize
echo [INFO] Waiting for backend to initialize...
timeout /t 5 >nul

:: 3. Start Frontend
echo [INFO] Starting Frontend...
echo [INFO] The browser should open automatically.
echo ==========================================
cd frontend
npm run dev

pause
