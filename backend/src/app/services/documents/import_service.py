"""Import of a Google Docs document by public link (story 1.4.4).

The API only validates the link shape and creates the rows — the
DOCX export happens in the worker (1.9.3), so the API never touches
the network. The worker later builds the export URL from the extracted
identifier, not from the user string, which closes SSRF.
"""

import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents import DocumentRecord, MaterialRole, SourceType
from src.app.exceptions.documents import InvalidGdocsUrlError
from src.app.interfaces.repositories.documents import (
    DocumentRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.repositories.users import UserRepositoryProtocol
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.services.documents.processing_limits import assert_processing_capacity

# `https://docs.google.com/document/d/{id}/...`: the identifier is the
# opaque segment right after ``/document/d/``; Sheets/Slides and other
# domains do not match. A trailing path (``/edit``, ``/export``) is
# allowed, the bare id link is not part of the contract.
_GDOCS_URL_RE = re.compile(r"^https://docs\.google\.com/document/d/([A-Za-z0-9_-]+)(/[^\s]*)?$")

# a stable placeholder for the not-yet-exported source object; the
# worker addresses the export by the identifier in source_uri
GDOCS_OBJECT_KEY_PREFIX = "gdocs"

GDOCS_MIME_TYPE = "application/vnd.google-apps.document"


def extract_gdocs_id(url: str) -> str:
    """Return the document identifier of a Google Docs link or raise 422."""
    match = _GDOCS_URL_RE.match(url.strip())
    if match is None:
        raise InvalidGdocsUrlError(extra={"url": url})
    return match.group(1)


class ImportService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        dispatcher: TaskDispatcher,
        documents: DocumentRepositoryProtocol,
        materials: UserMaterialRepositoryProtocol,
        users: UserRepositoryProtocol,
    ) -> None:
        self._session = session
        self._dispatcher = dispatcher
        self._documents = documents
        self._materials = materials
        self._users = users

    async def import_document(self, *, owner_id: UUID, url: str) -> DocumentRecord:
        # validation happens before the transaction: a bad link must not
        # even open one
        gdocs_id = extract_gdocs_id(url)
        try:
            await assert_processing_capacity(
                users=self._users,
                documents=self._documents,
                owner_id=owner_id,
            )
            document = await self._documents.create(
                owner_id=owner_id,
                # the real title is fetched by the worker during export
                title="Untitled",
                source_type=SourceType.GDOCS,
                source_uri=url,
                object_key=f"{GDOCS_OBJECT_KEY_PREFIX}/{gdocs_id}",
                mime_type=GDOCS_MIME_TYPE,
                size_bytes=0,
                checksum=f"{GDOCS_OBJECT_KEY_PREFIX}:{gdocs_id}"[:64],
            )
            await self._materials.create(
                user_id=owner_id,
                document_id=document.id,
                role=MaterialRole.OWNER,
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        # network call after commit, never inside the transaction
        await self._dispatcher.enqueue_parse(document.id)
        return document
