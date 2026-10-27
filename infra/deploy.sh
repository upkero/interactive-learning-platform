#!/usr/bin/env bash
# Deploy Grasp production stack on a VPS (see docs/adr/0009-deployment.md).
# Usage: run from the repository root: ./infra/deploy.sh
set -euo pipefail

# Script must work from the repo root regardless of where it was invoked from
cd "$(dirname "$0")/.."

# ------------------------------------------------------------------
# Secrets: backend/.env is required and must be readable only by owner
# ------------------------------------------------------------------
if [ ! -f "backend/.env" ]; then
    echo "ERROR: backend/.env not found." >&2
    echo "Copy backend/.env.example to backend/.env and fill in production secrets first." >&2
    exit 1
fi
chmod 600 backend/.env

echo "Pulling production images..."
docker compose -f infra/compose.yml -f infra/compose.prod.yml pull

echo "Starting services..."
docker compose -f infra/compose.yml -f infra/compose.prod.yml up -d --remove-orphans

echo "Deployment finished successfully."
