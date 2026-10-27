"""Liveness and readiness endpoints.

По правилам Grasp (PROJECT_CONTEXT.md, 1.4.1):
- ``/health/live`` — процесс жив, проверки нет.
- ``/health/ready`` — API готов принимать трафик: PostgreSQL (SELECT 1),
  Redis (PING) и MinIO (health/live, если хранилище настроено).
Внешняя LLM сознательно не проверяется: недоступность Anthropic/Ollama
не делает API неготовым, генерацией занимаются Celery-воркеры.
"""

import asyncio
from typing import Annotated

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.api.v1.dependencies import get_container
from src.app.bootstrap.container import ApplicationContainer
from src.app.core.settings.storage import get_storage_settings

router = APIRouter(prefix="/health", tags=["infra"])

# Readiness-проверки должны падать быстро, чтобы LB не ждал подвисший upstream
_CHECK_TIMEOUT_SECONDS = 5.0

ContainerDep = Annotated[ApplicationContainer, Depends(get_container)]


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


async def _check_db(session_factory: async_sessionmaker[AsyncSession]) -> str | None:
    try:
        async with session_factory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), _CHECK_TIMEOUT_SECONDS)
    except Exception:  # любая ошибка означает неготовность БД
        return "PostgreSQL unavailable"
    return None


async def _check_redis(client: aioredis.Redis) -> str | None:
    try:
        await asyncio.wait_for(client.ping(), _CHECK_TIMEOUT_SECONDS)
    except Exception:
        return "Redis unavailable"
    return None


async def _check_minio(endpoint_url: str) -> str | None:
    if not endpoint_url:
        # Хранилище не настроено — не считаем API неготовым
        return None
    try:
        async with httpx.AsyncClient(timeout=_CHECK_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{endpoint_url.rstrip('/')}/minio/health/live")
            response.raise_for_status()
    except (httpx.HTTPError, OSError):
        return "MinIO unavailable"
    return None


@router.get("/ready")
async def readiness(container: ContainerDep) -> dict[str, str]:
    storage_settings = get_storage_settings()
    errors = [
        message
        for message in await asyncio.gather(
            _check_db(container.session_factory),
            _check_redis(container.redis_client),
            _check_minio(storage_settings.endpoint_url),
        )
        if message
    ]
    if errors:
        raise HTTPException(status_code=503, detail="; ".join(errors))
    return {"status": "ok"}
