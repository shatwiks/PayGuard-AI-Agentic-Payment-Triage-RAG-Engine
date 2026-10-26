@echo off
title PayGuard Backend [Port 8000]
pushd "%~dp0"

echo ===============================================================================
echo                PAYGUARD AI: BACKEND API [FastAPI / Uvicorn]
echo ===============================================================================
echo.
echo Starting backend server on http://127.0.0.1:8000 ...
echo.

if exist ".venv\Scripts\python.exe" (
    call ".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
) else (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Backend service encountered an error and stopped.
    pause
)
