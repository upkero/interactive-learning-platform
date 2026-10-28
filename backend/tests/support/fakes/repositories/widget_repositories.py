"""In-memory fakes of the widget and quota repositories."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from src.app.contracts.quizzes import QuizAttemptRecord
from src.app.contracts.quota import LedgerEntry, LedgerOp
from src.app.contracts.widgets import (
    PrimitiveRecord,
    ReportReason,
    ReportRecord,
    UsageStatus,
    WidgetDescriptionRecord,
    WidgetKind,
    WidgetRecord,
    WidgetStatus,
    WidgetUsageDraft,
    WidgetUsageRecord,
)
from src.app.interfaces.repositories.quizzes import QuizAttemptRepositoryProtocol
from src.app.interfaces.repositories.quota import GenerationLedgerRepositoryProtocol
from src.app.interfaces.repositories.widgets import (
    PrimitiveRepositoryProtocol,
    ReportRepositoryProtocol,
    WidgetDescriptionRepositoryProtocol,
    WidgetRepositoryProtocol,
    WidgetUsageRepositoryProtocol,
)
from tests.support.time import now


class FakePrimitiveRepository(PrimitiveRepositoryProtocol):
    """Dict-backed stub mirroring PrimitiveRepository API."""

    def __init__(self) -> None:
        self._primitives: dict[str, PrimitiveRecord] = {}

    async def get(self, primitive_id: str) -> PrimitiveRecord | None:
        return self._primitives.get(primitive_id)

    async def list_all(self) -> list[PrimitiveRecord]:
        return sorted(self._primitives.values(), key=lambda p: p.id)

    async def upsert(
        self,
        *,
        primitive_id: str,
        version: str,
        description: str,
        modes: list[str],
        params_schema: dict[str, Any],
    ) -> PrimitiveRecord:
        created = PrimitiveRecord(
            id=primitive_id,
            version=version,
            description=description,
            modes=modes,
            params_schema=params_schema,
            updated_at=now(),
        )
        self._primitives[primitive_id] = created
        return created


class FakeWidgetRepository(WidgetRepositoryProtocol):
    """Dict-backed stub mirroring WidgetRepository API."""

    def __init__(self) -> None:
        self._widgets: dict[UUID, WidgetRecord] = {}

    async def get(self, widget_id: UUID) -> WidgetRecord | None:
        return self._widgets.get(widget_id)

    async def create(
        self,
        *,
        kind: WidgetKind,
        primitive_id: str | None = None,
        mode: str | None = None,
        params: dict[str, Any] | None = None,
        source_tsx: str | None = None,
        compiled_js: str | None = None,
        created_from_part_id: UUID | None = None,
    ) -> WidgetRecord:
        record = WidgetRecord(
            id=uuid4(),
            kind=kind,
            primitive_id=primitive_id,
            mode=mode,
            params=params,
            source_tsx=source_tsx,
            compiled_js=compiled_js,
            status=WidgetStatus.ACTIVE,
            canonical_id=None,
            version=1,
            created_from_part_id=created_from_part_id,
            created_at=now(),
        )
        self._widgets[record.id] = record
        return record

    async def set_status(self, widget_id: UUID, status: WidgetStatus) -> None:
        row = self._widgets.get(widget_id)
        if row is not None:
            self._widgets[widget_id] = replace(row, status=status)


class FakeWidgetDescriptionRepository(WidgetDescriptionRepositoryProtocol):
    """Dict-backed stub mirroring WidgetDescriptionRepository API."""

    def __init__(self) -> None:
        self._descriptions: dict[UUID, WidgetDescriptionRecord] = {}

    async def create(
        self,
        *,
        widget_id: UUID,
        text: str,
        is_paraphrase: bool,
        embedding: list[float],
    ) -> WidgetDescriptionRecord:
        record = WidgetDescriptionRecord(
            id=uuid4(),
            widget_id=widget_id,
            text=text,
            is_paraphrase=is_paraphrase,
            embedding=embedding,
            created_at=now(),
        )
        self._descriptions[record.id] = record
        return record

    async def list_by_widget(self, widget_id: UUID) -> list[WidgetDescriptionRecord]:
        return [d for d in self._descriptions.values() if d.widget_id == widget_id]


class FakeWidgetUsageRepository(WidgetUsageRepositoryProtocol):
    """Dict-backed stub mirroring WidgetUsageRepository API."""

    def __init__(self) -> None:
        self._usages: dict[UUID, WidgetUsageRecord] = {}

    async def get(self, usage_id: UUID) -> WidgetUsageRecord | None:
        return self._usages.get(usage_id)

    async def add_many(self, part_id: UUID, usages: Sequence[WidgetUsageDraft]) -> list[WidgetUsageRecord]:
        created: list[WidgetUsageRecord] = []
        for draft in usages:
            record = WidgetUsageRecord(
                id=uuid4(),
                part_id=part_id,
                widget_id=draft.widget_id,
                directive_ref=draft.directive_ref,
                params=draft.params,
                position=draft.position,
                status=draft.status,
                created_at=now(),
            )
            self._usages[record.id] = record
            created.append(record)
        return created

    async def set_status(self, usage_id: UUID, status: UsageStatus) -> None:
        row = self._usages.get(usage_id)
        if row is not None:
            self._usages[usage_id] = replace(row, status=status)


class FakeReportRepository(ReportRepositoryProtocol):
    """Dict-backed stub mirroring ReportRepository API."""

    def __init__(self) -> None:
        self._reports: dict[UUID, ReportRecord] = {}

    async def get_by_widget_and_user(self, widget_id: UUID, user_id: UUID) -> ReportRecord | None:
        for row in self._reports.values():
            if row.widget_id == widget_id and row.user_id == user_id:
                return row
        return None

    async def create_if_not_exists(
        self,
        *,
        widget_id: UUID,
        user_id: UUID,
        reason: ReportReason,
        part_id: UUID | None = None,
    ) -> ReportRecord | None:
        if await self.get_by_widget_and_user(widget_id, user_id) is not None:
            return None
        record = ReportRecord(
            id=uuid4(),
            widget_id=widget_id,
            user_id=user_id,
            part_id=part_id,
            reason=reason,
            created_at=now(),
        )
        self._reports[record.id] = record
        return record


class FakeQuizAttemptRepository(QuizAttemptRepositoryProtocol):
    """Dict-backed stub mirroring QuizAttemptRepository API."""

    def __init__(self) -> None:
        self._attempts: dict[UUID, QuizAttemptRecord] = {}

    async def create(
        self,
        *,
        user_id: UUID,
        part_id: UUID,
        quiz_key: str,
        answer: dict[str, Any],
        is_correct: bool,
    ) -> QuizAttemptRecord:
        record = QuizAttemptRecord(
            id=uuid4(),
            user_id=user_id,
            part_id=part_id,
            quiz_key=quiz_key,
            answer=answer,
            is_correct=is_correct,
            created_at=now(),
        )
        self._attempts[record.id] = record
        return record

    async def list_by_part(self, part_id: UUID) -> list[QuizAttemptRecord]:
        return [a for a in self._attempts.values() if a.part_id == part_id]


class FakeGenerationLedgerRepository(GenerationLedgerRepositoryProtocol):
    """List-backed stub mirroring GenerationLedgerRepository API."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._next_id = 1

    async def add(
        self,
        *,
        user_id: UUID,
        op: LedgerOp,
        delta: int,
        period_start: date,
        document_id: UUID | None = None,
        part_id: UUID | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            id=self._next_id,
            user_id=user_id,
            document_id=document_id,
            part_id=part_id,
            op=op,
            delta=delta,
            period_start=period_start,
            created_at=now(),
        )
        self._next_id += 1
        self._entries.append(entry)
        return entry

    async def sum_delta(self, user_id: UUID, period_start: date) -> int:
        return sum(e.delta for e in self._entries if e.user_id == user_id and e.period_start >= period_start)
