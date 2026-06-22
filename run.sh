#!/bin/bash
set -e

echo "=== Trinetra Run Script ==="

# 0. Python dependencies
echo "[1/5] Installing Python dependencies..."
pip install -r requirements.txt

# 1. Pipeline
echo "[2/5] Checking dataset..."
PROCESSED_OK=""
if [ -d "data/processed" ] && [ -n "$(ls -A data/processed/*.parquet 2>/dev/null)" ]; then
    PROCESSED_OK="yes"
fi

if [ "$1" == "--force" ] || [ -z "$PROCESSED_OK" ]; then
    if [ ! -f "data/raw/violations.csv" ]; then
        echo "ERROR: data/processed/*.parquet are missing AND data/raw/violations.csv is absent."
        echo "       Cannot run. Restore either the processed parquets or the raw CSV."
        exit 1
    fi
    echo "[3/5] Rebuilding processed data from raw CSV..."
    # NOTE: must use the module form (-m). Calling the file path directly
    # breaks the 'backend' package import.
    python -m backend.pipeline.build_dataset
    python -m backend.pipeline.precompute
else
    echo "[3/5] Processed data exists. Skipping pipeline. (Use ./run.sh --force to rebuild)"
fi

# 3. Backend
echo "[4/5] Starting FastAPI backend..."
uvicorn backend.app.main:app --port 8000 &
BACKEND_PID=$!

echo "Waiting for backend to be healthy..."
while ! curl -s http://127.0.0.1:8000/ > /dev/null; do
    sleep 1
done
echo "Backend is up!"

# 4. Frontend (Next.js v2 - Trinetra)
echo "[5/5] Starting Trinetra Next.js frontend..."
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
