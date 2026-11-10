"""create_llm_client factory unit tests: provider dispatch per spec 2.1."""

import pytest
from pydantic import SecretStr

from src.app.core.settings.llm import LLMSettings
from src.app.llm.claude_client import ClaudeClient
from src.app.llm.factory import create_llm_client
from src.app.llm.openai_compatible_llm_client import OpenAICompatibleLLMClient


@pytest.mark.unit
def test_anthropic_creates_claude_client() -> None:
    settings = LLMSettings(provider="anthropic", api_key=SecretStr("sk"), model="claude-x")

    client = create_llm_client(settings)

    assert isinstance(client, ClaudeClient)
    assert client.model_name == "claude-x"
    assert client.provider_name == "anthropic"


@pytest.mark.unit
def test_ollama_creates_openai_compatible_client_with_default_url() -> None:
    settings = LLMSettings(provider="ollama", model="llama3.2")

    client = create_llm_client(settings)

    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client.model_name == "llama3.2"
    assert str(client._client.base_url).rstrip("/").endswith("11434/v1")


@pytest.mark.unit
def test_openai_compatible_honors_custom_base_url() -> None:
    settings = LLMSettings(provider="openai_compatible", base_url="http://proxy:8080/v1", api_key=SecretStr("k"))

    client = create_llm_client(settings)

    assert isinstance(client, OpenAICompatibleLLMClient)
    assert str(client._client.base_url).rstrip("/") == "http://proxy:8080/v1"
