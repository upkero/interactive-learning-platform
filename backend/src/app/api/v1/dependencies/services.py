"""Dependencies of the services used by the API (story 1.4).

Session-scoped services are built per request with their repositories
bound to the request session; cross-request collaborators (storage,
dispatcher) come from the DI container. Test doubles are injected by
overriding these getters on the app.
"""

from typing import Annotated

from fastapi import Depends

from src.app.api.v1.dependencies.container import ContainerDep
from src.app.api.v1.dependencies.db import DBSessionDep
from src.app.core.settings.upload import get_upload_settings
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.documents.document_query_service import DocumentQueryService
from src.app.services.documents.file_inspector import FileInspector
from src.app.services.documents.upload_service import UploadService


def get_task_dispatcher(container: ContainerDep) -> TaskDispatcher:
    """Container-level dispatcher; tests override this with a recording fake."""
    return container.task_dispatcher


TaskDispatcherDep = Annotated[TaskDispatcher, Depends(get_task_dispatcher)]


def get_file_inspector() -> FileInspector:
    """Stateless content inspector bound to the upload settings."""
    return FileInspector(get_upload_settings())


FileInspectorDep = Annotated[FileInspector, Depends(get_file_inspector)]


def get_upload_service(
    session: DBSessionDep,
    container: ContainerDep,
    dispatcher: TaskDispatcherDep,
    inspector: FileInspectorDep,
) -> UploadService:
    return UploadService(
        session=session,
        inspector=inspector,
        storage=container.object_storage,
        dispatcher=dispatcher,
        documents=DocumentRepository(session),
        materials=UserMaterialRepository(session),
        users=UserRepository(session),
    )


UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]


def get_document_query_service(
    session: DBSessionDep,
    container: ContainerDep,
) -> DocumentQueryService:
    return DocumentQueryService(
        documents=DocumentRepository(session),
        materials=UserMaterialRepository(session),
        parts=DocumentPartRepository(session),
        storage=container.object_storage,
    )


DocumentQueryServiceDep = Annotated[DocumentQueryService, Depends(get_document_query_service)]


__all__ = [
    "DocumentQueryServiceDep",
    "FileInspectorDep",
    "TaskDispatcherDep",
    "UploadServiceDep",
    "get_document_query_service",
    "get_file_inspector",
    "get_task_dispatcher",
    "get_upload_service",
]
