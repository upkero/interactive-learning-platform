"""Liveness and readiness endpoints.

Readiness rules (story 1.4.1, platform observability):
- ``/health/live`` — the process is alive, no checks.
- ``/health/ready`` — the API can accept traffic: PostgreSQL (SELECT 1),
  Redis (PING) and MinIO (head_bucket of both buckets through
  ``ObjectStorageClient.ping()``: verifies reachability, credentials and
  that the buckets exist).
The external LLM is deliberately not checked: Anthropic/Ollama being
unavailable does not make the API not ready; generation runs in Celery
workers.
"""

import asyncio
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.api.v1.dependencies import get_container
from src.app.bootstrap.container import ApplicationContainer
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient

router = APIRouter(prefix="/health", tags=["infra"])

# Readiness checks must fail fast so the LB does not wait on a stuck upstream
_CHECK_TIMEOUT_SECONDS = 5.0

ContainerDep = Annotated[ApplicationContainer, Depends(get_container)]


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


async def _check_db(session_factory: async_sessionmaker[AsyncSession]) -> str | None:
    try:
        async with session_factory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), _CHECK_TIMEOUT_SECONDS)
    except Exception:  # any error means the database is not ready
        return "PostgreSQL unavailable"
    return None


async def _check_redis(client: aioredis.Redis) -> str | None:
    try:
        await asyncio.wait_for(client.ping(), _CHECK_TIMEOUT_SECONDS)
    except Exception:
        return "Redis unavailable"
    return None


async def _check_object_storage(storage: ObjectStorageClient) -> str | None:
    """head_bucket of both buckets: reachability, credentials, bucket existence."""
    try:
        await asyncio.wait_for(storage.ping(), _CHECK_TIMEOUT_SECONDS)
    except Exception:  # any error means MinIO is not ready for traffic
        return "MinIO unavailable"
    return None


@router.get("/ready")
async def readiness(container: ContainerDep) -> dict[str, str]:
    errors = [
        message
        for message in await asyncio.gather(
            _check_db(container.session_factory),
            _check_redis(container.redis_client),
            _check_object_storage(container.object_storage),
        )
        if message
    ]
    if errors:
        raise HTTPException(status_code=503, detail="; ".join(errors))
    return {"status": "ok"}
