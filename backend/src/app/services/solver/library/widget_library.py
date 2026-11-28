"""WidgetLibrary: facade over widget repositories (story 2.4)."""

import json
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.solver.resolve import ResolveOutcome
from src.app.contracts.solver.valid_config import ValidConfig
from src.app.contracts.widgets import (
    UsageStatus,
    WidgetDescriptionRecord,
    WidgetKind,
    WidgetRecord,
    WidgetUsageDraft,
    WidgetUsageRecord,
)
from src.app.interfaces.repositories.widgets import (
    PrimitiveRepositoryProtocol,
    WidgetDescriptionRepositoryProtocol,
    WidgetRepositoryProtocol,
    WidgetUsageRepositoryProtocol,
)

logger = logging.getLogger(__name__)

NUMBER_TOLERANCE = 0.05


def params_equal(a: Any, b: Any) -> bool:
    """Compare params with ±5% tolerance for numbers, exact for strings/arrays/bools."""
    # Bools must be identical (True != 1)
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b

    # Numbers: ±5% tolerance
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == b:
            return True
        max_abs = max(abs(a), abs(b))
        if max_abs == 0:
            return True
        return abs(a - b) <= NUMBER_TOLERANCE * max_abs

    # Dicts: same keys, all values equal recursively
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return False
        return all(params_equal(a[key], b[key]) for key in a)

    # Lists (arrays): exact canonical JSON equality
    if isinstance(a, list) and isinstance(b, list):
        return _canonical(a) == _canonical(b)

    # Everything else: exact equality
    return bool(a == b)


def _canonical(value: Any) -> str:
    """Canonical JSON representation for exact comparison."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class WidgetLibrary:
    """Facade for widget library operations: save, deduplicate, describe, usage."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        widget_repo: Callable[[AsyncSession], WidgetRepositoryProtocol],
        widget_desc_repo: Callable[[AsyncSession], WidgetDescriptionRepositoryProtocol],
        widget_usage_repo: Callable[[AsyncSession], WidgetUsageRepositoryProtocol],
        primitive_repo: Callable[[AsyncSession], PrimitiveRepositoryProtocol],
    ) -> None:
        self._session_factory = session_factory
        self._widget_repo = widget_repo
        self._widget_desc_repo = widget_desc_repo
        self._widget_usage_repo = widget_usage_repo
        self._primitive_repo = primitive_repo

    async def save_config(
        self,
        config: ValidConfig,
        *,
        part_id: UUID,
    ) -> tuple[UUID, bool]:
        """Save or deduplicate a widget configuration.

        Returns (widget_id, created_new). Uses advisory lock on (primitive_id, mode).
        """
        async with self._session_factory() as session, session.begin():
            lock_key = f"widget:{config.primitive_id}:{config.mode}"
            await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(lock_key))))

            widget_repo = self._widget_repo(session)

            # Check for existing active widget with same params
            for existing in await widget_repo.list_active_configs(config.primitive_id, config.mode):
                if params_equal(existing.params, config.params):
                    logger.info(
                        "Deduplicated widget: existing=%s, primitive=%s, mode=%s",
                        existing.id,
                        config.primitive_id,
                        config.mode,
                    )
                    return existing.id, False

            # Create new widget
            widget_id = await widget_repo.create_config(
                primitive_id=config.primitive_id,
                mode=config.mode,
                params=config.params,
                version=config.primitive_version,
                created_from_part_id=part_id,
            )
            logger.info(
                "Created new widget: id=%s, primitive=%s, mode=%s",
                widget_id,
                config.primitive_id,
                config.mode,
            )
            return widget_id, True

    async def save_code(
        self,
        *,
        primitive_id: str | None,
        mode: str | None,
        params: dict[str, Any],
        source_tsx: str,
        compiled_js: str,
        version: int,
        part_id: UUID,
    ) -> UUID:
        """Save a code widget (no deduplication; normalization in 2.8)."""
        async with self._session_factory() as session, session.begin():
            widget_repo = self._widget_repo(session)
            widget_record = await widget_repo.create(
                kind=WidgetKind.CODE,
                primitive_id=primitive_id,
                mode=mode,
                params=params,
                source_tsx=source_tsx,
                compiled_js=compiled_js,
                created_from_part_id=part_id,
            )
            return widget_record.id

    async def add_descriptions(
        self,
        widget_id: UUID,
        description: str,
        paraphrases: list[str],
        embeddings: list[list[float]],
    ) -> list[WidgetDescriptionRecord]:
        """Add main description + paraphrases with embeddings."""
        if len(embeddings) != 1 + len(paraphrases):
            raise ValueError("Expected 1 + len(paraphrases) embeddings")

        async with self._session_factory() as session, session.begin():
            desc_repo = self._widget_desc_repo(session)

            # Main description
            main_record = await desc_repo.create(
                widget_id=widget_id,
                text=description,
                is_paraphrase=False,
                embedding=embeddings[0],
            )

            # Paraphrases
            paraphrase_records = []
            for i, para in enumerate(paraphrases):
                record = await desc_repo.create(
                    widget_id=widget_id,
                    text=para,
                    is_paraphrase=True,
                    embedding=embeddings[i + 1],
                )
                paraphrase_records.append(record)

            return [main_record, *paraphrase_records]

    async def save_usage(
        self,
        part_id: UUID,
        outcome: ResolveOutcome,
        position: int = 0,
    ) -> WidgetUsageRecord:
        """Upsert widget_usage by (part_id, directive_ref)."""

        async with self._session_factory() as session, session.begin():
            usage_repo = self._widget_usage_repo(session)

            # Convert status from ResolveOutcome's literal to UsageStatus
            status = UsageStatus.READY if outcome.status == "ready" else UsageStatus.FALLBACK

            draft = WidgetUsageDraft(
                directive_ref=outcome.directive_ref,
                widget_id=outcome.widget_id,
                status=status,
                params=outcome.params,
                position=position,
            )

            records = await usage_repo.add_many(part_id, [draft])
            return records[0]

    async def list_active_configs(self, primitive_id: str, mode: str) -> list[WidgetRecord]:
        """List active widgets for a primitive+mode (for deduplication)."""
        async with self._session_factory() as session:
            widget_repo = self._widget_repo(session)
            return await widget_repo.list_active_configs(primitive_id, mode)


__all__ = ["WidgetLibrary"]
