#!/usr/bin/env bash

# Set strict error handling
set -euo pipefail

echo "🚀 Starting backend (Docker)..."

docker compose -f docker-compose.yaml -f docker-compose.dev.yaml up --build
