#!/usr/bin/env bash

# Set strict error handling
set -euo pipefail

# cd into the parent directory of the script,
cd "${0%/*}" || exit 1

cd ../

# echo "⚙️  Starting infrastructure..."

# Check if infrastructure is already running
# if docker compose -f docker-compose.infra.yaml ps | grep -q "Up"; then
#     echo "   Infrastructure already running, skipping startup..."
# else
#     docker compose -f docker-compose.infra.yaml up -d
# fi


echo "🚀 Starting backend..."

port=8000
host=127.0.0.1
uv run uvicorn "app.main:app" --host "$host" --port "$port" --reload
out=$?

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    # docker compose -f docker-compose.infra.yaml down
}

trap cleanup EXIT


if [ $out -ne 0 ]; then
    echo "❌ Failed to start backend"
    exit $out
fi
