#!/bin/bash
set -e

echo "=== Gridlock Run Script ==="

# 1. Pipeline
echo "[1/4] Checking dataset..."
if [ ! -f "data/raw/violations.csv" ]; then
    echo "ERROR: data/raw/violations.csv missing. Please place the raw data."
    exit 1
fi

echo "[2/4] Running pipeline (skips if data/processed/ is already populated, pass --force to rebuild)..."
if [ "$1" == "--force" ] || [ ! -d "data/processed" ] || [ -z "$(ls -A data/processed/*.parquet 2>/dev/null)" ]; then
    echo "Rebuilding processed data..."
    python backend/pipeline/build_dataset.py
    python backend/pipeline/precompute.py
else
    echo "Processed data exists. Skipping pipeline. (Use ./run.sh --force to rebuild)"
fi

# 3. Backend
echo "[3/4] Starting FastAPI backend..."
uvicorn backend.app.main:app --port 8000 &
BACKEND_PID=$!

echo "Waiting for backend to be healthy..."
while ! curl -s http://127.0.0.1:8000/ > /dev/null; do
    sleep 1
done
echo "Backend is up!"

# 4. Frontend (Next.js v2 - Trinetra)
echo "[4/4] Starting Trinetra Next.js frontend..."
cd frontend_v2
if [ ! -d "node_modules" ]; then
    echo "Installing Node dependencies..."
    npm install
fi
echo "Building Next.js app..."
npm run build
echo "Starting Next.js server..."
npm start &
FRONTEND_PID=$!

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
