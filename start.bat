@echo off
setlocal EnableDelayedExpansion

title PayGuard AI - Launcher
pushd "%~dp0"

echo ===============================================================================
echo                PAYGUARD AI: AGENTIC PAYMENT TRIAGE AND RAG ENGINE
echo ===============================================================================
echo.

:: 1. Verify Python Virtual Environment
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
    echo Please ensure the .venv folder is present in the project directory.
    echo.
    pause
    popd
    exit /b 1
)

:: 2. Verify Frontend Dependencies
if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend npm dependencies...
    pushd frontend
    call npm install
    popd
)

:: 3. Clear Port Conflicts on Ports 3000 and 8000
where docker >nul 2>&1
if !errorlevel! equ 0 (
    docker info >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%i in ('docker ps -q --filter "publish=3000"') do (
            echo [INFO] Stopping conflicting Docker container on port 3000 [%%i]...
            docker stop %%i >nul 2>&1
        )
        for /f "tokens=*" %%i in ('docker ps -q --filter "publish=8000"') do (
            echo [INFO] Stopping conflicting Docker container on port 8000 [%%i]...
            docker stop %%i >nul 2>&1
        )
    )
)

:: 4. Check and Start PostgreSQL Database (Port 5434)
echo [1/4] Checking PostgreSQL Database on port 5434...
netstat -ano | findstr ":5434" | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo       Database is active on port 5434.
) else (
    echo       Starting database container via Docker...
    where docker >nul 2>&1
    if !errorlevel! equ 0 (
        docker info >nul 2>&1
        if !errorlevel! neq 0 (
            echo       Launching Docker Desktop...
            if exist "C:\Users\shatw\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe" (
                start "" "C:\Users\shatw\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"
            ) else if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
                start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
            )
            ping 127.0.0.1 -n 12 >nul
        )
        docker start payguard_postgres >nul 2>&1
        if !errorlevel! neq 0 (
            docker compose up -d db >nul 2>&1
        )
        ping 127.0.0.1 -n 4 >nul
        echo       Database container initialized.
    ) else (
        echo       Warning: Docker not found. Ensure PostgreSQL is running on port 5434.
    )
)

:: 5. Check and Start Ollama Engine (Port 11434)
echo.
echo [2/4] Checking Ollama Engine on port 11434...
netstat -ano | findstr ":11434" | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo       Ollama is active on port 11434.
) else (
    where ollama >nul 2>&1
    if !errorlevel! equ 0 (
        echo       Starting Ollama daemon...
        start "Ollama Engine" /min cmd /c "ollama serve"
        ping 127.0.0.1 -n 4 >nul
        echo       Ollama daemon started.
    ) else (
        echo       Notice: Ollama command not found in PATH.
    )
)

:: 6. Start Backend API (FastAPI on Port 8000)
echo.
echo [3/4] Starting PayGuard Backend API on port 8000...
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo       Backend API is already running on port 8000.
) else (
    start "PayGuard Backend [Port 8000]" cmd /k "run_backend.bat"
    echo       Backend API launching in separate window...
    set /a RETRIES=0
    :WAIT_BACKEND
    ping 127.0.0.1 -n 2 >nul
    netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
    if !errorlevel! neq 0 (
        set /a RETRIES+=1
        if !RETRIES! lss 15 goto WAIT_BACKEND
    )
    echo       Backend API is ready on http://127.0.0.1:8000.
)

:: 7. Start Frontend Application (Next.js on Port 3000)
echo.
echo [4/4] Starting PayGuard Frontend on port 3000...
netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo       Frontend is already running on port 3000.
) else (
    start "PayGuard Frontend [Port 3000]" cmd /k "run_frontend.bat"
    echo       Frontend launching in separate window...
    set /a RETRIES=0
    :WAIT_FRONTEND
    ping 127.0.0.1 -n 2 >nul
    netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
    if !errorlevel! neq 0 (
        set /a RETRIES+=1
        if !RETRIES! lss 20 goto WAIT_FRONTEND
    )
    echo       Frontend is ready on http://localhost:3000.
)

:: 8. Open Default Browser
echo.
echo Opening PayGuard AI in your default browser...
ping 127.0.0.1 -n 3 >nul
start http://localhost:3000

echo.
echo ===============================================================================
echo                PAYGUARD AI APPLICATION IS RUNNING!
echo ===============================================================================
echo.
echo   * Web Application:   http://localhost:3000
echo   * Backend API:       http://localhost:8000/api/v1
echo   * API Documentation: http://localhost:8000/api/v1/docs
echo   * Database Port:     5434 [PostgreSQL + pgvector]
echo   * Ollama Port:       11434 [llama3.1:8b and nomic-embed-text]
echo.
echo   Keep the Backend and Frontend command prompt windows open while working.
echo   To shut down all services cleanly at any time, run 'stop.bat'.
echo.
echo ===============================================================================
echo Press any key to close this launcher window [services will remain running]...
pause >nul
popd
