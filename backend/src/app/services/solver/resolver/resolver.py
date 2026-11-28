"""Main resolver algorithm (story 2.4).

Turns a widget directive into a WidgetUsage via a cascade of stages:
search → rerank → reuse/configure → synthesize → fallback.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from uuid import UUID

from src.app.contracts.solver.degradation import Degradation
from src.app.contracts.solver.resolve import ResolveOutcome, ResolveRequest
from src.app.contracts.solver.valid_config import ValidConfig
from src.app.contracts.solver.widget_candidate import WidgetCandidate
from src.app.interfaces.observability.metrics_collector import MetricsCollector
from src.app.services.solver.library.widget_library import WidgetLibrary
from src.app.services.solver.resolver.config_assembler import ConfigAssembler
from src.app.services.solver.resolver.config_validator import ConfigValidator
from src.app.services.solver.resolver.describer import Describer
from src.app.services.solver.resolver.fallback import fallback_outcome
from src.app.services.solver.resolver.llm_outputs import ConfigDraft
from src.app.services.solver.resolver.reranker import Reranker
from src.app.services.solver.search.widget_search import WidgetSearch

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RESOLVE_DURATION = "widget_resolver.resolve_duration_seconds"
_RESOLVED_COUNTER = "widget_resolver.resolved"
_UNRESOLVED_COUNTER = "widget_resolver.unresolved"
_DECISION_COUNTER = "widget_resolver.decisions_total"


class Resolver:
    """Strict resolver: errors propagate outward."""

    def __init__(
        self,
        *,
        search: WidgetSearch,
        reranker: Reranker,
        assembler: ConfigAssembler,
        validator: ConfigValidator,
        library: WidgetLibrary,
        describer: Describer,
        code_generator: Any | None = None,  # Story 2.5
        metrics: MetricsCollector,
    ) -> None:
        self._search = search
        self._reranker = reranker
        self._assembler = assembler
        self._validator = validator
        self._library = library
        self._describer = describer
        self._code_generator = code_generator
        self._metrics = metrics

    async def resolve(self, request: ResolveRequest) -> ResolveOutcome:
        """Resolve one directive to a WidgetUsage outcome."""
        trail: list[Degradation] = []

        outcome = await self._decide(request, trail)

        # Record decision metrics
        self._metrics.increment_counter(
            _DECISION_COUNTER,
            by=1,
            labels={"decision": outcome.decision},
        )

        # Save usage
        await self._library.save_usage(request.part_id, outcome)

        return outcome

    async def _decide(
        self,
        request: ResolveRequest,
        trail: list[Degradation],
    ) -> ResolveOutcome:
        directive = request.directive

        # Stage 1: Search
        primitive_hint = None
        if directive.primitive_hint in self._assembler._catalog:
            primitive_hint = directive.primitive_hint

        candidates: list[WidgetCandidate] = await self._stage(
            trail,
            "search",
            "configure",
            default=[],
            action=lambda: self._search.search(
                directive.intent,
                k=5,
                primitive_hint=primitive_hint,
            ),
        )

        if not candidates:
            return fallback_outcome(directive)

        # Stage 2: Rerank
        verdict = await self._stage(
            trail,
            "rerank",
            "configure",
            default=None,
            action=lambda: self._reranker.choose(directive, candidates),
        )

        if verdict is not None and verdict.choice is not None:
            chosen = candidates[ord(verdict.choice[1]) - ord("1")]
            if verdict.fits_as_is:
                # Stage 3a: Reuse as-is
                reused = await self._stage(
                    trail,
                    "reuse",
                    "configure",
                    default=None,
                    action=lambda: self._reuse(request, chosen),
                )
                if reused is not None:
                    return reused

        # Stage 4: Configure (build or adapt)
        configured = await self._stage(
            trail,
            "configure",
            "synthesize",
            default=None,
            action=lambda: self._configure(request, trail),
        )
        if configured is not None:
            return configured

        # Stage 5: Synthesize (story 2.5)
        if self._code_generator is not None:
            generated = await self._stage(
                trail,
                "synthesize",
                "fallback",
                default=None,
                action=lambda: self._synthesize(request, trail),
            )
            if generated is not None:
                return generated

        # Stage 6: Fallback
        return fallback_outcome(directive)

    async def _stage(
        self,
        trail: list[Degradation],
        stage: str,
        fallback: str,
        *,
        default: T,
        action: Callable[[], Awaitable[T]],
    ) -> T:
        """Execute a stage; in strict mode, let exceptions propagate."""
        return await action()

    async def _reuse(
        self,
        request: ResolveRequest,
        candidate: WidgetCandidate,
    ) -> ResolveOutcome | None:
        """Reuse candidate as-is or adapt params."""
        if candidate.kind.name == "CODE":
            # For code widgets, check shape compatibility
            return ResolveOutcome(
                directive_ref=request.directive.ref,
                decision="reused",
                status="ready",
                widget_id=candidate.widget_id,
                params=candidate.params or {},
            )

        # For config widgets, adapt params
        config = await self._assembler.adapt(candidate, request.directive)
        if config is None:
            return None

        check = await self._validator.check(request.directive, config)
        if not check.ok:
            return None

        widget_id, _ = await self._library.save_config(config, part_id=request.part_id)
        return ResolveOutcome(
            directive_ref=request.directive.ref,
            decision="configured",
            status="ready",
            widget_id=widget_id,
            params=config.params,
        )

    async def _configure(
        self,
        request: ResolveRequest,
        trail: list[Degradation],
    ) -> ResolveOutcome | None:
        """Build and validate a new configuration."""
        config = await self._assembler.build(request.directive)
        if config is None:
            return None

        check = await self._validator.check(request.directive, config)
        if not check.ok:
            # One fix attempt - need to convert ValidConfig to ConfigDraft
            draft = ConfigDraft(
                primitive_id=config.primitive_id,
                mode=config.mode,
                params_json=json.dumps(config.params),
                reason="auto-generated for fix attempt",
            )
            fixed = await self._assembler.fix(request.directive, draft, check.issues)
            if fixed is None:
                return None
            check = await self._validator.check(request.directive, fixed)
            if not check.ok:
                return None
            config = fixed

        widget_id, created = await self._library.save_config(config, part_id=request.part_id)

        if created:
            # Generate descriptions
            await self._stage(
                trail,
                "describe",
                "unindexed_widget",
                default=None,
                action=lambda: self._describe_new_widget(widget_id, config),
            )

        return ResolveOutcome(
            directive_ref=request.directive.ref,
            decision="configured",
            status="ready",
            widget_id=widget_id,
            params=config.params,
        )

    async def _describe_new_widget(
        self,
        widget_id: UUID,
        config: ValidConfig,
    ) -> None:
        """Generate and save descriptions for a new config widget."""
        # Get primitive record for description
        # This would need a primitive repo - simplified for now
        pass

    async def _synthesize(
        self,
        request: ResolveRequest,
        trail: list[Degradation],
    ) -> ResolveOutcome | None:
        """Code generation path (story 2.5)."""
        if self._code_generator is None:
            return None
        # Placeholder for story 2.5
        return None


class DegradingResolver(Resolver):
    """Resolver that catches exceptions and degrades to the next stage."""

    async def _stage(
        self,
        trail: list[Degradation],
        stage: str,
        fallback: str,
        *,
        default: T,
        action: Callable[[], Awaitable[T]],
    ) -> T:
        try:
            return await action()
        except Exception as exc:  # CancelledError is BaseException, not caught
            logger.warning(
                "Resolver stage %s failed, falling back to %s.",
                stage,
                fallback,
                exc_info=True,
            )
            trail.append(Degradation(stage=stage, reason=type(exc).__name__, fallback=fallback))
            return default


class InstrumentedResolver(Resolver):
    """Resolver with decision logging and metrics."""

    def __init__(
        self,
        *,
        search: WidgetSearch,
        reranker: Reranker,
        assembler: ConfigAssembler,
        validator: ConfigValidator,
        library: WidgetLibrary,
        describer: Describer,
        code_generator: Any | None = None,
        metrics: MetricsCollector,
        decision_log: Any,  # DecisionLog from observability
    ) -> None:
        super().__init__(
            search=search,
            reranker=reranker,
            assembler=assembler,
            validator=validator,
            library=library,
            describer=describer,
            code_generator=code_generator,
            metrics=metrics,
        )
        self._decision_log = decision_log

    async def resolve(self, request: ResolveRequest) -> ResolveOutcome:
        trail: list[Degradation] = []
        outcome = await self._decide(request, trail)

        # Log decision
        if self._decision_log:
            await self._decision_log.log_resolver_decision(
                part_id=request.part_id,
                directive_ref=request.directive.ref,
                decision=outcome.decision,
                widget_id=outcome.widget_id,
                candidates=[],  # Would need to pass candidates
                degradations=trail,
            )

        self._metrics.increment_counter(
            _DECISION_COUNTER,
            by=1,
            labels={"decision": outcome.decision},
        )

        await self._library.save_usage(request.part_id, outcome)
        return outcome


__all__ = ["DegradingResolver", "InstrumentedResolver", "Resolver"]