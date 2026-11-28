"""Describer: writes descriptions for new widgets (story 2.4.6)."""

import logging
from uuid import UUID

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.contracts.solver.valid_config import ValidConfig
from src.app.contracts.widgets import PrimitiveRecord
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.structured import call_structured
from src.app.services.solver.resolver.llm_outputs import WidgetDescriptionDraft
from src.app.services.solver.resolver.prompts import (
    DESCRIBE_CODE_SYSTEM_PROMPT,
    DESCRIBE_CONFIG_SYSTEM_PROMPT,
    render_describe_code_prompt,
    render_describe_config_prompt,
)

logger = logging.getLogger(__name__)


class Describer:
    """Generates descriptions and paraphrases for new widgets."""

    def __init__(self, cheap_llm: LLMClient) -> None:
        self._llm = cheap_llm

    async def describe_config(
        self,
        widget_id: UUID,
        config: ValidConfig,
        primitive_record: PrimitiveRecord,
    ) -> WidgetDescriptionDraft:
        """Describe a config widget from its primitive, mode, and actual params."""
        prompt = render_describe_config_prompt(
            primitive_description=primitive_record.description,
            mode=config.mode,
            params=config.params,
        )

        try:
            draft = await call_structured(
                self._llm,
                LLMRequest(
                    purpose="describe",
                    messages=(LLMMessage(role="user", content=prompt),),
                    system=(SystemBlock(text=DESCRIBE_CONFIG_SYSTEM_PROMPT, cache=True),),
                ),
                WidgetDescriptionDraft,
            )
            return draft
        except Exception as exc:
            logger.warning("Describer.describe_config failed: %s", exc)
            raise

    async def describe_code(
        self,
        widget_id: UUID,
        source_tsx: str,
        screenshot_base64: str,
    ) -> WidgetDescriptionDraft:
        """Describe a code widget from its TSX and a screenshot."""
        prompt = render_describe_code_prompt(source_tsx, screenshot_base64)

        try:
            draft = await call_structured(
                self._llm,
                LLMRequest(
                    purpose="describe",
                    messages=(LLMMessage(role="user", content=prompt),),
                    system=(SystemBlock(text=DESCRIBE_CODE_SYSTEM_PROMPT, cache=True),),
                ),
                WidgetDescriptionDraft,
            )
            return draft
        except Exception as exc:
            logger.warning("Describer.describe_code failed: %s", exc)
            raise


__all__ = ["Describer"]
