"""Main pass of the solver (story 2.2): one main-model call per part.

The pass is the only step that sees the whole part text, so it carries the
heaviest request of the resolver. The prompt is split into the cached
layers described in ``prompts.py``; the output is a validated ``PageDraft``
whose directives the resolver (2.4) and the quiz generator (2.6) fulfil
independently, and whose offsets the screen (Э6) uses to place the results.

Semantic rules that need part context (image aliases, widget limit, two
widgets in a row with the same primitive and mode) are checked after the
structured call. A violation is sent back for exactly one repair turn; a
violation that survives it is sanitised: the second widget loses
``mode_hint`` and the resolver picks the mode itself. The share of
first-answer violations goes to the decision log as a counter and a
structured warning, so the prompt can be tuned on the corpus.
"""

import logging
from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.solver.main_pass import (
    MainPassInput,
    MainPassResult,
    PartImage,
)
from src.app.contracts.widgets import PrimitiveRecord
from src.app.core.log_context import bind_log_context
from src.app.core.settings.solver import SolverSettings
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.interfaces.observability.metrics_collector import MetricsCollector
from src.app.interfaces.repositories.widgets import PrimitiveRepositoryProtocol
from src.app.llm.structured import call_structured
from src.app.observability.decision_log import DecisionLog
from src.app.services.solver.main_pass.directive_parser import (
    UnrecoverableDraftError,
    Violation,
    ViolationCode,
    extract_markers,
    find_violations,
    sanitize_draft,
)
from src.app.services.solver.main_pass.directives import PageDraft, RecoveredPageDraft
from src.app.services.solver.main_pass.prompts import (
    PROMPT_VERSION,
    build_main_pass_request,
    build_retry_request,
)
from src.app.services.solver.main_pass.source_spans import locate_spans

logger = logging.getLogger(__name__)

_VIOLATION_COUNTER = "main_pass.draft_violations_total"


class MainPassService:
    """Rewrite one part for one reader and return the page draft."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        session_factory: async_sessionmaker[AsyncSession],
        primitives: Callable[[AsyncSession], PrimitiveRepositoryProtocol],
        settings: SolverSettings,
        metrics: MetricsCollector,
    ) -> None:
        self._llm = llm
        self._session_factory = session_factory
        self._primitives = primitives
        self._settings = settings
        self._metrics = metrics
        self._decisions = DecisionLog(metrics=metrics)

    async def run(self, payload: MainPassInput) -> MainPassResult:
        catalog = await self._load_catalog()
        request = self._request(payload, catalog)
        with bind_log_context(document_id=str(payload.document_id), part_id=str(payload.part_id)):
            model_draft = await call_structured(self._llm, request, PageDraft)
            draft: RecoveredPageDraft = model_draft
            violations = self._violations(model_draft, payload)
            self._metrics.increment_counter(
                "main_pass.drafts_total", labels={"first_answer": "violations" if violations else "clean"}
            )
            self._decisions.main_pass_first_draft(
                prompt_version=PROMPT_VERSION,
                violation_count=len(violations),
                alternation_violation_count=sum(
                    issue.code == ViolationCode.REPEATED_WIDGET_MODE for issue in violations
                ),
            )
            retried = bool(violations)
            if violations:
                self._record_violations(violations, attempt="first")
                retry_request = build_retry_request(request, model_draft, violations)
                draft = await call_structured(self._llm, retry_request, PageDraft)
                remaining = self._violations(draft, payload)
                if remaining:
                    self._record_violations(remaining, attempt="retry")
                    draft = sanitize_draft(
                        draft,
                        max_widgets=self._settings.max_widgets_per_part,
                        max_quizzes=self._settings.max_quizzes_per_part,
                        image_aliases={image.alias for image in payload.images},
                    )
            if self._violations(draft, payload):
                raise UnrecoverableDraftError("Unresolved final draft violations")
            markers, _ = extract_markers(draft.markdown)
            by_ref = {directive.ref: directive for directive in draft.directives}
            draft = draft.model_copy(update={"directives": [by_ref[m.ref] for m in markers]})
            result = MainPassResult(
                draft=draft.to_draft(),
                spans=locate_spans(draft.directives, payload.part_markdown),
                image_ids=self._image_ids(draft, payload.images),
            )
            logger.info(
                "Main pass completed.",
                extra={
                    "directives": len(result.draft.directives),
                    "key_terms": len(result.draft.key_terms),
                    "markdown_chars": len(result.draft.markdown),
                    "retried": retried,
                },
            )
            return result

    async def _load_catalog(self) -> Sequence[PrimitiveRecord]:
        async with self._session_factory() as session:
            return await self._primitives(session).list_all()

    def _request(self, payload: MainPassInput, catalog: Sequence[PrimitiveRecord]) -> LLMRequest:
        return build_main_pass_request(payload, catalog, self._settings)

    def _violations(self, draft: RecoveredPageDraft, payload: MainPassInput) -> list[Violation]:
        return find_violations(
            draft.markdown,
            draft.directives,
            image_aliases={image.alias for image in payload.images},
            max_widgets=self._settings.max_widgets_per_part,
            max_quizzes=self._settings.max_quizzes_per_part,
            alternation=True,
            key_terms=draft.key_terms,
        )

    def _record_violations(self, violations: Sequence[Violation], *, attempt: str) -> None:
        self._metrics.increment_counter(_VIOLATION_COUNTER, labels={"attempt": attempt}, by=len(violations))
        logger.warning(
            "Main pass rule violation.",
            extra={"attempt": attempt, "violation_count": len(violations)},
        )

    @staticmethod
    def _image_ids(draft: RecoveredPageDraft, images: Sequence[PartImage]) -> dict[str, UUID]:
        by_alias = {image.alias: image.id for image in images}
        return {
            directive.image_id: by_alias[directive.image_id]
            for directive in draft.directives
            if directive.kind == "image" and directive.image_id is not None and directive.image_id in by_alias
        }


__all__ = ["MainPassService"]
