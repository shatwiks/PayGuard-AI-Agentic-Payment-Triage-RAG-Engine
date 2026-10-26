@echo off
title PayGuard Frontend [Port 3000]
pushd "%~dp0frontend"

echo ===============================================================================
echo                PAYGUARD AI: FRONTEND APPLICATION [Next.js]
echo ===============================================================================
echo.
echo Starting Next.js frontend on http://localhost:3000 ...
echo.

call npm run dev

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Frontend service encountered an error and stopped.
    pause
)
