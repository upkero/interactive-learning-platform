"""Structured call with schema validation and one retry.

Services never parse JSON by hand: they define a pydantic model and call
``call_structured``. On ``LLMSchemaError`` the error text goes into the last
message as a hint ("Ответ не прошёл проверку схемы: …") and the request is
retried exactly once. Network/429 retries belong to the SDK — our own
retries are applied only to schema errors.
"""

from dataclasses import replace

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.exceptions.llm import LLMSchemaError
from src.app.interfaces.llm.llm_client import LLMClient


async def call_structured[T: BaseModel](
    llm: LLMClient,
    request: LLMRequest,
    schema: type[T],
    *,
    retries: int = 1,
) -> T:
    """Execute the structured call and return a schema instance."""
    attempt_request = request
    for attempt in range(retries + 1):
        try:
            return (await llm.complete_structured(attempt_request, schema)).value
        except LLMSchemaError as exc:
            if attempt == retries:
                raise
            attempt_request = replace(
                request,
                messages=(
                    *request.messages,
                    LLMMessage(
                        role="user",
                        content=f"Ответ не прошёл проверку схемы: {exc}. Верни исправленный JSON.",
                    ),
                ),
            )
    raise AssertionError("unreachable")
