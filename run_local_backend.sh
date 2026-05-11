#!/bin/bash

# ============================================================================
# Local Backend Quick Start Script (Mac/Linux)
# ============================================================================
# This script sets up and starts the local backend in one command

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Federated Learning Backend - LOCAL SETUP & START           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Change to backend directory
cd federated_learning_backend

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "[1/5] Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        echo "Make sure Python 3.8+ is installed"
        exit 1
    fi
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

echo ""
echo "[2/5] Activating virtual environment..."
source venv/bin/activate

echo "[3/5] Installing dependencies..."
pip install -r requirements.txt -q
if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo "✅ Dependencies installed"

echo ""
echo "[4/5] Running database migrations..."
python manage.py migrate -q
if [ $? -ne 0 ]; then
    echo "❌ Failed to run migrations"
    exit 1
fi
echo "✅ Database ready"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              🚀 BACKEND STARTING...                            ║"
echo "║                                                                ║"
echo "║  Backend URL: http://localhost:8000                           ║"
echo "║  API URL:     http://localhost:8000/api/fl/                  ║"
echo "║  Admin URL:   http://localhost:8000/admin                     ║"
echo "║                                                                ║"
echo "║  📱 In Flutter Config:                                        ║"
echo "║     Set: useLocalBackend = true                               ║"
echo "║                                                                ║"
echo "║  Press Ctrl+C to stop                                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

python manage.py runserver 0.0.0.0:8000
