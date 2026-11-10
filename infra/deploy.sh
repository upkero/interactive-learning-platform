#!/usr/bin/env bash
# Deploy Grasp production stack on a VPS (see docs/adr/0009-deployment.md).
# Usage (from the repository root):
#   IMAGE_TAG=<commit-sha-published-by-CI> ./infra/deploy.sh
set -euo pipefail

# Script must work from the repo root regardless of where it was invoked from
cd "$(dirname "$0")/.."

# ------------------------------------------------------------------
# IMAGE_TAG: задан явно (sha коммита из CI), чтобы деплой был
# воспроизводимым и без туманных тегов вида latest
# ------------------------------------------------------------------
if [ -z "${IMAGE_TAG:-}" ]; then
    echo "ERROR: IMAGE_TAG is not set." >&2
    echo "Pass the commit sha that CI published to GHCR, e.g.:" >&2
    echo "  IMAGE_TAG=<commit-sha> ./infra/deploy.sh" >&2
    exit 1
fi

# Secrets: backend/.env is required and must be readable only by owner
# ------------------------------------------------------------------
if [ ! -f "backend/.env" ]; then
    echo "ERROR: backend/.env not found." >&2
    echo "Copy backend/.env.example to backend/.env and fill in production secrets first." >&2
    exit 1
fi
chmod 600 backend/.env

# MinIO: каталог данных должен существовать и быть XFS
# ------------------------------------------------------
# Свежие AIStor-сборки отказываются форматировать ext4-тома и остаются
# офлайн («drives-online: 0», каждый S3-запрос — 403). Разовая настройка
# диска описана в docs/minio-xfs.md.
MINIO_DATA_DIR="$(grep -E '^MINIO_DATA_DIR=' backend/.env | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs)"
if [ -z "$MINIO_DATA_DIR" ]; then
    echo "ERROR: MINIO_DATA_DIR is not set in backend/.env." >&2
    echo "Point it at an XFS directory prepared per docs/minio-xfs.md." >&2
    exit 1
fi
if [ ! -d "$MINIO_DATA_DIR" ]; then
    echo "ERROR: MINIO_DATA_DIR '$MINIO_DATA_DIR' does not exist." >&2
    echo "Prepare the XFS drive per docs/minio-xfs.md first." >&2
    exit 1
fi
if [ ! "$(stat -f -c %T "$MINIO_DATA_DIR")" = "xfs" ]; then
    echo "ERROR: $MINIO_DATA_DIR is not on an XFS filesystem (found: $(stat -f -c %T "$MINIO_DATA_DIR"))." >&2
    echo "MinIO AIStor builds refuse ext4-backed drives; see docs/minio-xfs.md." >&2
    exit 1
fi

echo "Pulling production images (tag: ${IMAGE_TAG})..."
docker compose --env-file backend/.env -f infra/compose.yml -f infra/compose.prod.yml pull

echo "Starting services..."
docker compose --env-file backend/.env -f infra/compose.yml -f infra/compose.prod.yml up -d --remove-orphans

echo "Deployment finished successfully."
