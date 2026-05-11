@echo off
REM ============================================================================
REM Local Backend Quick Start Script (Windows)
REM ============================================================================
REM This script sets up and starts the local backend in one command

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║     Federated Learning Backend - LOCAL SETUP & START           ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Change to backend directory
cd federated_learning_backend

REM Check if venv exists
if not exist "venv\" (
    echo [1/5] Creating virtual environment...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ Failed to create virtual environment
        echo Make sure Python 3.8+ is installed and python is in PATH
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

echo.
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/5] Installing dependencies...
pip install -r requirements.txt -q
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)
echo ✅ Dependencies installed

echo.
echo [4/5] Running database migrations...
python manage.py migrate -q
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Failed to run migrations
    pause
    exit /b 1
)
echo ✅ Database ready

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              🚀 BACKEND STARTING...                            ║
echo ║                                                                ║
echo ║  Backend URL: http://localhost:8000                           ║
echo ║  API URL:     http://localhost:8000/api/fl/                  ║
echo ║  Admin URL:   http://localhost:8000/admin                     ║
echo ║                                                                ║
echo ║  📱 In Flutter Config:                                        ║
echo ║     Set: useLocalBackend = true                               ║
echo ║                                                                ║
echo ║  Press Ctrl+C to stop                                          ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

python manage.py runserver 0.0.0.0:8000

pause
