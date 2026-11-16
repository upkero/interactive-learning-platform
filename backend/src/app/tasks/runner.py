"""Run one async task with resources bound to its own event loop."""

import asyncio
from collections.abc import Awaitable, Callable

from src.app.bootstrap.container import ApplicationContainer
from src.app.core.log_context import bind_log_context


def run_async[T](fn: Callable[[ApplicationContainer], Awaitable[T]], **log_context: str) -> T:
    async def main() -> T:
        container = ApplicationContainer()
        try:
            with bind_log_context(**log_context):
                return await fn(container)
        finally:
            await container.close()

    return asyncio.run(main())
