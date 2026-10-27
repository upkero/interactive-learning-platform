"""Claude client over the native Anthropic SDK.

Structured output goes through ``messages.create`` with
``output_config={"format": {"type": "json_schema", ...}}`` (2.1.1): the API
constrains generation to the schema, and we additionally validate the reply
locally with ``schema.model_validate_json``. The reply text, ``stop_reason``
and usage are read from typed SDK models (``Message``, ``TextBlock``,
``Usage``).

The only place that constructs ``AsyncAnthropic`` is ``llm/factory.py``;
the SDK client arrives here ready-made (tests build one over a mocked HTTP
transport). SDK errors are mapped to our exceptions (exceptions/llm.py) and
never escape llm/. Network and 429 retries belong to the SDK (max_retries
setting).

Sampling parameters (``temperature``/``top_p``/``top_k``) are intentionally
not sent: the current Anthropic API rejects any non-default value on
claude-sonnet-5-5, so ``LLMRequest.temperature`` is silently ignored here.

Cache caveat: a cached block must exceed the model's minimum cacheable
length (512 tokens for claude-sonnet-5-5, 4096 for claude-haiku-4-5) — a
shorter block is silently not cached.
See https://docs.claude.com/en/docs/build-with-claude/prompt-caching.
"""

from collections.abc import Sequence
from dataclasses import asdict

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import ImageBlockParam, MessageParam, TextBlock, TextBlockParam, Usage
from pydantic import BaseModel, ValidationError

from src.app.contracts.llm.image_part import ImagePart
from src.app.contracts.llm.llm_message import LLMContent, LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse, TokenUsage
from src.app.contracts.llm.system_block import SystemBlock
from src.app.core.settings.llm import LLMSettings
from src.app.exceptions.llm import LLMGenerationError, LLMRateLimitError, LLMSchemaError
from src.app.interfaces.llm.llm_client import LLMClient


class ClaudeClient(LLMClient):
    def __init__(self, *, settings: LLMSettings, client: AsyncAnthropic) -> None:
        self._settings = settings
        self._client = client

    @property
    def model_name(self) -> str:
        return self._settings.model

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        """Plain text completion.

        Not used by the resolver (every resolver call goes through
        ``complete_structured``); kept for compatibility with the template
        interface.
        """
        try:
            response = await self._client.messages.create(
                model=self._settings.model,
                max_tokens=self._settings.max_tokens or 4096,
                messages=[self._message(m) for m in messages],
            )
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError() from exc
        except anthropic.APIError as exc:
            raise LLMGenerationError("Claude request failed.") from exc

        text = self._text(response)
        if not text:
            raise LLMGenerationError("Claude returned empty content.")
        return LLMResponse(
            content=text,
            model=response.model,
            finish_reason=response.stop_reason,
            usage=asdict(usage) if (usage := self._usage(response.usage)) is not None else None,
        )

    async def complete_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> StructuredResponse[T]:
        try:
            response = await self._client.messages.create(
                model=self._settings.model,
                max_tokens=request.max_tokens,
                system=self._system_blocks(request.system),
                messages=[self._message(m) for m in request.messages],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": anthropic.transform_schema(schema.model_json_schema()),
                    }
                },
            )
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError() from exc
        except anthropic.APIError as exc:
            raise LLMGenerationError("Claude request failed.") from exc

        # The API returns schema violations as plain text (or truncates the
        # reply), so the failure mode is visible only through stop_reason.
        if response.stop_reason == "refusal":
            raise LLMGenerationError("Claude refused the request.")
        if response.stop_reason == "max_tokens":
            raise LLMSchemaError("Claude output was cut off by max_tokens before the JSON schema was satisfied.")

        text = self._text(response)
        try:
            value = schema.model_validate_json(text)
        except ValidationError as exc:
            raise LLMSchemaError(f"Response failed schema validation: {exc}") from exc

        return StructuredResponse(value=value, usage=self._usage(response.usage))

    async def ping(self) -> bool:
        try:
            await self._client.models.list()
        except anthropic.APIError:
            return False
        return True

    async def close(self) -> None:
        await self._client.close()

    @staticmethod
    def _text(response: anthropic.types.Message) -> str:
        return "".join(block.text for block in response.content if isinstance(block, TextBlock))

    @staticmethod
    def _system_blocks(blocks: tuple[SystemBlock, ...]) -> list[TextBlockParam]:
        result: list[TextBlockParam] = []
        for block in blocks:
            item: TextBlockParam
            if block.cache:
                item = {"type": "text", "text": block.text, "cache_control": {"type": "ephemeral"}}
            else:
                item = {"type": "text", "text": block.text}
            result.append(item)
        return result

    def _message(self, message: LLMMessage) -> MessageParam:
        return {"role": message.role, "content": self._content(message.content)}

    @staticmethod
    def _content(content: LLMContent) -> str | list[TextBlockParam | ImageBlockParam]:
        if isinstance(content, str):
            return content
        parts: list[TextBlockParam | ImageBlockParam] = []
        for part in content:
            if isinstance(part, ImagePart):
                parts.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": part.media_type,
                            "data": part.data_base64,
                        },
                    }
                )
            else:
                parts.append({"type": "text", "text": part.text})
        return parts

    @staticmethod
    def _usage(usage: Usage | None) -> TokenUsage | None:
        if usage is None:
            return None
        return TokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_input_tokens=usage.cache_read_input_tokens or 0,
            cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
        )
