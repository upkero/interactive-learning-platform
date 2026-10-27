"""Claude client over the native Anthropic SDK.

The native SDK provides two things missing in the OpenAI-compatible layer:
structured output (``messages.parse`` + ``output_format``) and prompt
caching (``cache_control`` on system blocks).

The only place that constructs ``AsyncAnthropic`` is ``llm/factory.py``;
the SDK client arrives here ready-made (handy for tests with a fake).
SDK errors are mapped to our exceptions (exceptions/llm.py) and never
escape llm/. Network and 429 retries belong to the SDK (max_retries setting).

Cache caveat: Anthropic requires at least ~1024 tokens (2048 for Haiku)
in a cached block — a short system prompt cannot be cached.
"""

from collections.abc import Sequence

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import ImageBlockParam, MessageParam, TextBlockParam
from pydantic import BaseModel

from src.app.contracts.llm.image_part import ImagePart
from src.app.contracts.llm.llm_message import LLMContent, LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse, TokenUsage
from src.app.contracts.llm.system_block import SystemBlock
from src.app.core.settings.llm import LLMSettings
from src.app.exceptions.llm import LLMGenerationError, LLMRateLimitError, LLMSchemaError
from src.app.interfaces.llm.llm_client import LLMClient

# Anthropic requires at least ~1024 tokens (2048 for Haiku) in a cached block;
# block order is fixed by MainPass: the immutable system prompt comes first,
# volatile content goes strictly after.


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

        text = "".join(getattr(block, "text", "") for block in response.content)
        if not text:
            raise LLMGenerationError("Claude returned empty content.")
        return LLMResponse(
            content=text,
            model=getattr(response, "model", None) or self.model_name,
            finish_reason=getattr(response, "stop_reason", None),
            usage=self._usage_to_mapping(getattr(response, "usage", None)),
        )

    async def complete_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> StructuredResponse[T]:
        try:
            response = await self._client.messages.parse(
                model=self._settings.model,
                max_tokens=request.max_tokens,
                system=self._system_blocks(request.system),
                messages=[self._message(m) for m in request.messages],
                output_format=schema,
            )
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError() from exc
        except anthropic.APIError as exc:
            raise LLMGenerationError("Claude request failed.") from exc

        if response.parsed_output is None:
            raise LLMSchemaError("Model returned no parsed output.")

        return StructuredResponse(
            value=response.parsed_output,
            usage=self._usage(getattr(response, "usage", None)),
        )

    async def ping(self) -> bool:
        try:
            await self._client.models.list()
        except anthropic.APIError:
            return False
        return True

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            await close()

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
    def _usage(usage: object) -> TokenUsage | None:
        if usage is None:
            return None
        return TokenUsage(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )

    @staticmethod
    def _usage_to_mapping(usage: object) -> dict[str, int] | None:
        token_usage = ClaudeClient._usage(usage)
        if token_usage is None:
            return None
        return {
            "input_tokens": token_usage.input_tokens,
            "output_tokens": token_usage.output_tokens,
            "cache_read_input_tokens": token_usage.cache_read_input_tokens,
            "cache_creation_input_tokens": token_usage.cache_creation_input_tokens,
        }
