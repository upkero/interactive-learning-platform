"""OpenAI-compatible client (Ollama, OpenRouter, etc.).

Structured output goes through ``response_format`` with JSON Schema (2.1.2):
we hand the provider the pydantic schema and validate the reply with
``schema.model_validate_json``. Prompt caching is not available in the
OpenAI-compatible API, so ``SystemBlock.cache`` is ignored here.
"""

from collections.abc import Sequence
from typing import Literal, cast

import openai
from openai import AsyncOpenAI, OpenAIError
from openai.lib._pydantic import to_strict_json_schema
from openai.types import CompletionUsage
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionAssistantMessageParam,
    ChatCompletionContentPartParam,
    ChatCompletionMessageParam,
    ChatCompletionUserMessageParam,
    CompletionCreateParams,
)
from openai.types.chat.chat_completion import Choice
from pydantic import BaseModel, ValidationError

from src.app.contracts.llm.image_part import ImagePart
from src.app.contracts.llm.llm_message import LLMContent, LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse, TokenUsage
from src.app.core.settings.llm import LLMSettings
from src.app.exceptions.llm import LLMGenerationError, LLMInputError, LLMRateLimitError, LLMSchemaError
from src.app.interfaces.llm.llm_client import LLMClient


class OpenAICompatibleLLMClient(LLMClient):
    def __init__(
        self,
        *,
        settings: LLMSettings,
        client: AsyncOpenAI,
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
        params: CompletionCreateParams = {
            "model": self._settings.model,
            "messages": self._chat_messages(request),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    # to_strict_json_schema is what the SDK itself uses in
                    # chat.completions.parse: OpenAI's strict mode requires
                    # additionalProperties:false and all fields in required,
                    # which a plain model_json_schema() does not satisfy
                    # (the API answers 400). Private module — keep this
                    # import inside llm/ only.
                    "schema": to_strict_json_schema(schema),
                    "strict": True,
                },
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
        content = choice.message.content
        if content is None:
            raise LLMSchemaError("Model returned no parsed output.")

        try:
            value = schema.model_validate_json(content)
        except ValidationError as exc:
            raise LLMSchemaError(f"Response failed schema validation: {exc}") from exc

        return StructuredResponse(value=value, usage=self._token_usage(completion.usage))

    async def ping(self) -> bool:
        try:
            await self._client.models.list()
        except OpenAIError:
            return False
        return True

    async def close(self) -> None:
        await self._client.close()

    def _chat_messages(self, request: LLMRequest) -> list[ChatCompletionMessageParam]:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": block.text} for block in request.system
        ]
        # Literal roles let mypy pick the exact TypedDict per branch.
        for message in request.messages:
            if message.role == "user":
                user: ChatCompletionUserMessageParam = {"role": "user", "content": self._content(message.content)}
                messages.append(user)
            else:
                # Grasp never attaches images to assistant messages: the
                # provider rejects image parts there, so the cast is safe.
                messages.append(
                    cast(
                        "ChatCompletionAssistantMessageParam",
                        {"role": "assistant", "content": self._content(message.content)},
                    )
                )
        return messages

    def _completion_params(self, messages: Sequence[LLMMessage]) -> CompletionCreateParams:
        built: list[ChatCompletionMessageParam] = []
        for message in messages:
            if message.role == "user":
                user: ChatCompletionUserMessageParam = {"role": "user", "content": self._content(message.content)}
                built.append(user)
            else:
                built.append(
                    cast(
                        "ChatCompletionAssistantMessageParam",
                        {"role": "assistant", "content": self._content(message.content)},
                    )
                )
        params: CompletionCreateParams = {
            "model": self._settings.model,
            "messages": built,
        }
        if self._settings.temperature is not None:
            params["temperature"] = self._settings.temperature
        if self._settings.max_tokens is not None:
            params["max_tokens"] = self._settings.max_tokens
        if self._settings.reasoning_effort is not None:
            # Settings store the value as str; the SDK API takes the Literal
            # set OpenAI accepts. The set is mirrored here for mypy.
            params["reasoning_effort"] = cast(
                "Literal['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']",
                self._settings.reasoning_effort,
            )
        return params

    @staticmethod
    def _content(content: LLMContent) -> str | list[ChatCompletionContentPartParam]:
        if isinstance(content, str):
            return content
        parts: list[ChatCompletionContentPartParam] = []
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

    def _build_response(self, completion: ChatCompletion) -> LLMResponse:
        choice = self._first_choice(completion)
        content = choice.message.content
        if content is None:
            raise LLMGenerationError("LLM provider returned empty message content.")

        return LLMResponse(
            content=content,
            model=completion.model,
            finish_reason=choice.finish_reason,
            usage=self._token_usage(completion.usage),
            metadata=self._metadata(completion),
        )

    @staticmethod
    def _first_choice(completion: ChatCompletion) -> Choice:
        choices = completion.choices
        if not choices:
            raise LLMGenerationError("LLM provider returned no choices.")
        return choices[0]

    @staticmethod
    def _token_usage(usage: CompletionUsage | None) -> TokenUsage | None:
        if usage is None:
            return None
        details = usage.prompt_tokens_details
        # prompt_tokens_details and cached_tokens are both optional in the
        # CompletionUsage contract (providers may omit them).
        return TokenUsage(
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            cache_read_input_tokens=(details.cached_tokens if details is not None else 0) or 0,
        )

    @staticmethod
    def _metadata(completion: ChatCompletion) -> dict[str, object]:
        return {"id": completion.id, "created": completion.created}
