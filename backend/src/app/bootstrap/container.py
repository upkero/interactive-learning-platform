import inspect
from functools import cached_property

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.app.core.settings.app import get_app_settings
from src.app.core.settings.llm import get_llm_settings
from src.app.db.session import build_engine, build_session_factory
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.factory import create_llm_client


class ApplicationContainer:
    @cached_property
    def llm_client(self) -> LLMClient:
        return create_llm_client(get_llm_settings())

    @cached_property
    def _db_engine(self) -> AsyncEngine:
        settings = get_app_settings()
        return build_engine(str(settings.db_url))

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
