#!/usr/bin/env bash

# Set strict error handling
set -euo pipefail

echo "🚀 Starting backend (Docker)..."

# Start the prod Docker environment
docker compose -f docker-compose.yaml up --build