"""OpenAI-compatible client (Ollama, OpenRouter, etc.).

Structured output goes through ``response_format`` with JSON Schema (2.1.2):
we hand the provider the pydantic schema and validate the reply with
``schema.model_validate_json``. Prompt caching is not available in the
OpenAI-compatible API, so ``SystemBlock.cache`` is ignored here.
"""

from collections.abc import Sequence
from typing import Any

import openai
from openai import OpenAIError
from pydantic import BaseModel, ValidationError

from src.app.contracts.llm.image_part import ImagePart
from src.app.contracts.llm.llm_message import LLMContent, LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse, TokenUsage
from src.app.core.settings.llm import LLMSettings
from src.app.exceptions.llm import LLMGenerationError, LLMInputError, LLMRateLimitError, LLMSchemaError
from src.app.interfaces.llm.llm_client import LLMClient

_USAGE_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


class OpenAICompatibleLLMClient(LLMClient):
    def __init__(
        self,
        *,
        settings: LLMSettings,
        client: Any,
    ) -> None:
        self._settings = settings
        self._client = client

    @property
    def model_name(self) -> str:
        return self._settings.model

    @property
    def provider_name(self) -> str:
        return self._settings.provider

    @property
    def price_prompt_per_1m(self) -> float | None:
        return self._settings.price_prompt_per_1m

    @property
    def price_completion_per_1m(self) -> float | None:
        return self._settings.price_completion_per_1m

    async def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        if not messages:
            raise LLMInputError("LLM messages must not be empty.")

        try:
            completion = await self._client.chat.completions.create(
                **self._completion_params(messages),
            )
        except openai.RateLimitError as exc:
            raise LLMRateLimitError() from exc
        except OpenAIError as exc:
            raise LLMGenerationError("LLM provider request failed.") from exc

        return self._build_response(completion)

    async def complete_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> StructuredResponse[T]:
        params: dict[str, object] = {
            "model": self._settings.model,
            "messages": self._chat_messages(request),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            },
            "max_tokens": request.max_tokens,
        }
        if request.temperature is not None:
            params["temperature"] = request.temperature

        try:
            completion = await self._client.chat.completions.create(**params)
        except openai.RateLimitError as exc:
            raise LLMRateLimitError() from exc
        except OpenAIError as exc:
            raise LLMGenerationError("LLM provider request failed.") from exc

        choice = self._first_choice(completion)
        content = getattr(getattr(choice, "message", None), "content", None)
        if not content or not isinstance(content, str):
            raise LLMSchemaError("Model returned no parsed output.")

        try:
            value = schema.model_validate_json(content)
        except ValidationError as exc:
            raise LLMSchemaError(f"Response failed schema validation: {exc}") from exc

        return StructuredResponse(
            value=value,
            usage=self._token_usage(getattr(completion, "usage", None)),
        )

    async def ping(self) -> bool:
        try:
            await self._client.models.list()
        except OpenAIError:
            return False
        return True

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            await close()

    def _chat_messages(self, request: LLMRequest) -> list[dict[str, object]]:
        messages: list[dict[str, object]] = [
            {"role": "system", "content": block.text} for block in request.system
        ]
        messages.extend(
            {"role": message.role, "content": self._content(message.content)}
            for message in request.messages
        )
        return messages

    def _completion_params(self, messages: Sequence[LLMMessage]) -> dict[str, object]:
        params: dict[str, object] = {
            "model": self._settings.model,
            "messages": [
                {
                    "role": message.role,
                    "content": self._content(message.content),
                }
                for message in messages
            ],
        }
        if self._settings.temperature is not None:
            params["temperature"] = self._settings.temperature
        if self._settings.max_tokens is not None:
            params["max_tokens"] = self._settings.max_tokens
        if self._settings.reasoning_effort is not None:
            params["reasoning_effort"] = self._settings.reasoning_effort
        return params

    @staticmethod
    def _content(content: LLMContent) -> str | list[dict[str, object]]:
        if isinstance(content, str):
            return content
        parts: list[dict[str, object]] = []
        for part in content:
            if isinstance(part, ImagePart):
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{part.media_type};base64,{part.data_base64}"},
                    }
                )
            else:
                parts.append({"type": "text", "text": part.text})
        return parts

    def _build_response(self, completion: Any) -> LLMResponse:
        choice = self._first_choice(completion)
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if content is None:
            raise LLMGenerationError("LLM provider returned empty message content.")

        return LLMResponse(
            content=content,
            model=getattr(completion, "model", None) or self.model_name,
            finish_reason=getattr(choice, "finish_reason", None),
            usage=self._usage_to_mapping(getattr(completion, "usage", None)),
            metadata=self._metadata(completion),
        )

    @staticmethod
    def _first_choice(completion: Any) -> Any:
        choices = getattr(completion, "choices", None) or []
        if not choices:
            raise LLMGenerationError("LLM provider returned no choices.")
        return choices[0]

    @staticmethod
    def _usage_to_mapping(usage: Any) -> dict[str, int] | None:
        if usage is None:
            return None
        result: dict[str, int] = {}
        for field in _USAGE_FIELDS:
            value = getattr(usage, field, None)
            if isinstance(value, int):
                result[field] = value
        return result or None

    @staticmethod
    def _token_usage(usage: Any) -> TokenUsage | None:
        if usage is None:
            return None
        details = getattr(usage, "prompt_tokens_details", None)
        return TokenUsage(
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cache_read_input_tokens=getattr(details, "cached_tokens", 0) or 0,
        )

    @staticmethod
    def _metadata(completion: Any) -> dict[str, object]:
        metadata: dict[str, object] = {}
        completion_id = getattr(completion, "id", None)
        created = getattr(completion, "created", None)
        if completion_id is not None:
            metadata["id"] = completion_id
        if created is not None:
            metadata["created"] = created
        return metadata
