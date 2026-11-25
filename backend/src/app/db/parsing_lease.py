"""A per-document PostgreSQL lease spanning the entire ingest operation."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class PostgresParsingLease:
    """Prevent concurrent delivery while allowing retries after worker death.

    Session-level advisory locks survive the short database transactions used
    by ingest. The dedicated connection is returned to the pool only after it
    has explicitly released its lock (or after PostgreSQL disconnects it).
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def acquire(self, document_id: UUID) -> AsyncIterator[bool]:
        key = int.from_bytes(document_id.bytes[:8], byteorder="big", signed=True)
        async with self._engine.connect() as connection:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            acquired = bool(await connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}))
            try:
                yield acquired
            finally:
                if acquired:
                    await connection.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
