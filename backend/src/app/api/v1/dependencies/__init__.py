"""FastAPI dependencies, split into files by domain (see the lead requirement)."""

from src.app.api.v1.dependencies.container import ContainerDep, get_container
from src.app.api.v1.dependencies.db import DBSessionDep, get_db_session
from src.app.api.v1.dependencies.llm import LLMClientDep, get_llm_client
from src.app.api.v1.dependencies.storage import ObjectStorageClientDep, get_object_storage

__all__ = [
    "ContainerDep",
    "DBSessionDep",
    "LLMClientDep",
    "ObjectStorageClientDep",
    "get_container",
    "get_db_session",
    "get_llm_client",
    "get_object_storage",
]
