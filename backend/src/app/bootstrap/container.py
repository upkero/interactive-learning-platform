import inspect
from functools import cached_property
from logging import getLogger

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.app.core.settings.app import get_app_settings
from src.app.core.settings.celery import get_celery_settings
from src.app.core.settings.llm import CheapLLMSettings, LLMSettings, get_cheap_llm_settings, get_llm_settings
from src.app.db.session import build_engine, build_session_factory
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.interfaces.observability.metrics_collector import MetricsCollectorProtocol
from src.app.llm.factory import create_llm_client
from src.app.llm.instrumented_llm_client import InstrumentedLLMClient
from src.app.observability.noop_metrics_collector import NoopMetricsCollector


class ApplicationContainer:
    @cached_property
    def llm_settings(self) -> LLMSettings:
        return get_llm_settings()

    @cached_property
    def cheap_llm_overrides(self) -> CheapLLMSettings:
        return get_cheap_llm_settings()

    @cached_property
    def metrics_collector(self) -> MetricsCollectorProtocol:
        # The real Prometheus exporter arrives with story 1.9.
        return NoopMetricsCollector()

    @cached_property
    def main_llm(self) -> LLMClient:
        return InstrumentedLLMClient(
            client=create_llm_client(self.llm_settings),
            logger=getLogger("grasp.llm"),
            metrics=self.metrics_collector,
        )

    @cached_property
    def cheap_llm(self) -> LLMClient:
        return InstrumentedLLMClient(
            client=create_llm_client(self.cheap_llm_overrides.resolve(self.llm_settings)),
            logger=getLogger("grasp.llm.cheap"),
            metrics=self.metrics_collector,
        )

    @cached_property
    def redis_client(self) -> aioredis.Redis:
        # Async Redis client for readiness probes and progress streams.
        redis_client: aioredis.Redis = aioredis.Redis.from_url(get_celery_settings().broker_url)
        return redis_client

    @cached_property
    def _db_engine(self) -> AsyncEngine:
        settings = get_app_settings()
        return build_engine(
            str(settings.db_url),
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            null_pool=settings.db_use_null_pool,
        )

    @cached_property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return build_session_factory(self._db_engine)

    async def close(self) -> None:
        closed_dependency_ids: set[int] = set()
        for dependency in tuple(self.__dict__.values()):
            dependency_id = id(dependency)
            if dependency_id in closed_dependency_ids:
                continue
            close = getattr(dependency, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result
            closed_dependency_ids.add(dependency_id)

        if "_db_engine" in self.__dict__:
            await self._db_engine.dispose()
