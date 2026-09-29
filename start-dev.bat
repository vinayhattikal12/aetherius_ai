@echo off
title Aetherius AI Platform Launcher
cd /d "%~dp0"

echo ========================================================
echo               AETHERIUS AI PLATFORM
echo          Phase 1: Foundation + Hardware + DB
echo ========================================================
echo.

:: 1. Check if PostgreSQL cluster is running or initialize local data
if not exist "data\postgres" (
    echo [1/3] Initializing local PostgreSQL cluster...
    mkdir "data\postgres" 2>nul
    initdb -D "data\postgres" -U postgres -A trust
    createdb -h localhost -p 54329 -U postgres aetherius 2>nul
)

echo [1/3] Starting PostgreSQL (Port 54329)...
start "Aetherius Database" /B pg_ctl -D "data\postgres" -l "data\postgres\server.log" -o "-p 54329" start
timeout /t 2 /nobreak >nul

:: 2. Start FastAPI Backend
echo [2/3] Starting Aetherius Core (FastAPI)...
start "Aetherius Core" cmd /k ".\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 2 /nobreak >nul

:: 3. Start Desktop Application
echo [3/3] Starting Aetherius Desktop (Electron + React)...
cd /d "%~dp0apps\desktop"
npm start
