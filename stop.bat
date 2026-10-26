@echo off
setlocal EnableDelayedExpansion

title PayGuard AI - Shutdown Manager
pushd "%~dp0"

echo ===============================================================================
echo                PAYGUARD AI: SHUTDOWN MANAGER
echo ===============================================================================
echo.

:: 1. Terminate Backend on Port 8000
echo [1/2] Stopping Backend on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":8000\>.*LISTENING"') do (
    set PID=%%a
    if defined PID (
        taskkill /F /PID !PID! >nul 2>&1
        echo       Terminated process !PID! on port 8000.
    )
)
where docker >nul 2>&1
if !errorlevel! equ 0 (
    docker info >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%i in ('docker ps -q --filter "publish=8000"') do (
            docker stop %%i >nul 2>&1
            echo       Stopped Docker container on port 8000 [%%i].
        )
    )
)

:: 2. Terminate Frontend on Port 3000
echo [2/2] Stopping Frontend on port 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":3000\>.*LISTENING"') do (
    set PID=%%a
    if defined PID (
        taskkill /F /PID !PID! >nul 2>&1
        echo       Terminated process !PID! on port 3000.
    )
)
where docker >nul 2>&1
if !errorlevel! equ 0 (
    docker info >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%i in ('docker ps -q --filter "publish=3000"') do (
            docker stop %%i >nul 2>&1
            echo       Stopped Docker container on port 3000 [%%i].
        )
    )
)

echo.
echo ===============================================================================
echo   PayGuard AI frontend and backend have been successfully stopped.
echo   (PostgreSQL and Ollama services remain ready for your next session.)
echo ===============================================================================
echo.
pause
popd
