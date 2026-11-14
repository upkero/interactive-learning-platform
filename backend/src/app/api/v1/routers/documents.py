"""Document endpoints: upload (1.4.3) and read (1.4.3+).

The router is a thin adapter: it converts schemas into service calls
and service contracts into response schemas. Domain errors are not
caught here — the exception handlers (1.4.1) turn them into the unified
error format.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, UploadFile
from fastapi.params import Form

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import (
    DocumentQueryServiceDep,
    ImportServiceDep,
    UploadServiceDep,
)
from src.app.contracts.documents import DocumentDetails
from src.app.schemas.documents import (
    DocumentCreatedOut,
    DocumentImportIn,
    DocumentOut,
    PartSummaryOut,
    SharedWithOut,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=201, response_model=DocumentCreatedOut, operation_id="documents_upload")
async def upload_document(
    file: UploadFile,
    user: CurrentUserDep,
    service: UploadServiceDep,
    title: Annotated[str | None, Form(max_length=200)] = None,
) -> DocumentCreatedOut:
    document = await service.upload(
        owner_id=user.id,
        filename=file.filename,
        title=title,
        stream=file,
    )
    return DocumentCreatedOut(id=document.id, status=document.status.value)


@router.post(
    "/import",
    status_code=201,
    response_model=DocumentCreatedOut,
    operation_id="documents_import",
)
async def import_document(
    body: DocumentImportIn,
    user: CurrentUserDep,
    service: ImportServiceDep,
) -> DocumentCreatedOut:
    document = await service.import_document(owner_id=user.id, url=body.url)
    return DocumentCreatedOut(id=document.id, status=document.status.value)


@router.get("/{document_id}", response_model=DocumentOut, operation_id="documents_get")
async def get_document(
    document_id: UUID,
    user: CurrentUserDep,
    service: DocumentQueryServiceDep,
) -> DocumentOut:
    details: DocumentDetails = await service.get_document(user_id=user.id, document_id=document_id)
    document = details.document
    return DocumentOut(
        id=document.id,
        title=document.title,
        status=document.status.value,
        error_code=document.error,
        page_count=document.page_count,
        role=details.role.value,
        source_url=details.source_url,
        parts=[
            PartSummaryOut(id=part.id, index=part.index, title=part.title, status=part.status.value)
            for part in details.parts
        ],
        shared_with=[
            SharedWithOut(
                display_name=shared.display_name,
                email=shared.email,
                shared_at=shared.shared_at,
            )
            for shared in details.shared_with
        ],
    )


__all__ = ["router"]
