"""ConfigValidator: validates widget configurations (story 2.4.4)."""

import logging
from dataclasses import dataclass

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.contracts.solver.main_pass import MainPassDirective
from src.app.contracts.solver.valid_config import ValidConfig
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.structured import call_structured
from src.app.services.solver.resolver.llm_outputs import IntentCheck
from src.app.services.solver.resolver.prompts import (
    INTENT_CHECK_SYSTEM_PROMPT,
    render_intent_check_prompt,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of configuration validation."""

    ok: bool
    issues: list[str]


class ConfigValidator:
    """Validates configurations: jsonschema, mode, then intent match."""

    def __init__(self, cheap_llm: LLMClient) -> None:
        self._llm = cheap_llm

    async def check(
        self,
        request: MainPassDirective,
        config: ValidConfig,
    ) -> ValidationResult:
        """Full validation: schema + mode + intent (only if schema ok)."""
        # Schema and mode already validated in ConfigAssembler
        # Here we only do the intent check with the cheap model

        try:
            verdict = await call_structured(
                self._llm,
                LLMRequest(
                    purpose="config_check",
                    messages=(LLMMessage(role="user", content=render_intent_check_prompt(request, config)),),
                    system=(SystemBlock(text=INTENT_CHECK_SYSTEM_PROMPT, cache=True),),
                ),
                IntentCheck,
            )
        except Exception as exc:
            logger.warning("ConfigValidator.check call failed: %s", exc)
            raise

        if not verdict.matches:
            return ValidationResult(ok=False, issues=verdict.issues)

        return ValidationResult(ok=True, issues=[])


__all__ = ["ConfigValidator", "ValidationResult"]