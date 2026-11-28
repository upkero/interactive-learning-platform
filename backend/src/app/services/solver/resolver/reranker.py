"""Reranker: cheap model re-ranks widget candidates (story 2.4.1)."""

import logging
from collections.abc import Sequence

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.contracts.solver.main_pass import MainPassDirective
from src.app.contracts.solver.widget_candidate import WidgetCandidate
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.structured import call_structured
from src.app.services.solver.resolver.llm_outputs import RerankVerdict
from src.app.services.solver.resolver.prompts import (
    RERANK_SYSTEM_PROMPT,
    render_rerank_prompt,
)

logger = logging.getLogger(__name__)


class Reranker:
    """Chooses the best widget candidate using a cheap LLM."""

    def __init__(self, cheap_llm: LLMClient) -> None:
        self._llm = cheap_llm

    async def choose(
        self,
        request: MainPassDirective,
        candidates: Sequence[WidgetCandidate],
    ) -> RerankVerdict | None:
        """Return the reranker's verdict, or None if no candidates."""
        if not candidates:
            return None

        prompt = render_rerank_prompt(request, list(candidates))
        try:
            verdict = await call_structured(
                self._llm,
                LLMRequest(
                    purpose="rerank",
                    messages=(LLMMessage(role="user", content=prompt),),
                    system=(SystemBlock(text=RERANK_SYSTEM_PROMPT, cache=True),),
                ),
                RerankVerdict,
            )
            return verdict
        except Exception as exc:
            logger.warning("Reranker call failed: %s", exc)
            raise


__all__ = ["Reranker"]