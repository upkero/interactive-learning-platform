"""LLM client dependency."""

from typing import Annotated

from fastapi import Depends

from src.app.api.v1.dependencies.container import ContainerDep
from src.app.interfaces.llm.llm_client import LLMClient


def get_llm_client(container: ContainerDep) -> LLMClient:
    return container.llm_client


LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
