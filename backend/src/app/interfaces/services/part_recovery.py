"""Worker-facing contract for recovering timed-out parts."""

from collections.abc import Iterable
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.progress import ProgressEvent
from src.app.contracts.progress.recovery import RecoveryOutcome


class PartRecoveryProtocol(Protocol):
    """The part of ``PartRecovery`` used by the watchdog."""

    async def retry_or_fail_in(self, session: AsyncSession, part: PartRecord, *, reason: str) -> RecoveryOutcome: ...

    async def publish(self, events: Iterable[ProgressEvent]) -> None: ...
