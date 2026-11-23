import re

import httpx

from src.app.contracts.documents.statuses import DocumentErrorCode
from src.app.core.settings.ingest import get_ingest_settings

_GDOCS_RE = re.compile(
    r"^https://docs\.google\.com/document/(?:u/\d+/)?d/(?!e/)([A-Za-z0-9][A-Za-z0-9_-]*)(?:/[^?\s]*)?(?:\?[^\s]*)?$"
)


class GDocsImportError(Exception):
    def __init__(self, code: DocumentErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class GDocsImporter:
    def __init__(self, *, max_bytes: int | None = None, client: httpx.AsyncClient | None = None) -> None:
        self._max_bytes = max_bytes or get_ingest_settings().gdocs_max_bytes
        self._client = client

    async def fetch(self, url: str) -> tuple[bytes, str | None]:
        match = _GDOCS_RE.match(url.strip())
        if match is None:
            raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Invalid Google Docs URL")
        export_url = f"https://docs.google.com/document/d/{match.group(1)}/export?format=docx"
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(follow_redirects=True, timeout=30.0)
        try:
            async with client.stream("GET", export_url) as response:
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" in content_type:
                    raise GDocsImportError(DocumentErrorCode.GDOCS_NOT_PUBLIC, "Google Docs document is not public")
                if response.status_code >= 400:
                    raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Google Docs export failed")
                length = int(response.headers.get("content-length", "0") or 0)
                if length > self._max_bytes:
                    raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Google Docs export is too large")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self._max_bytes:
                        raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Google Docs export is too large")
                    chunks.append(chunk)
                title = response.headers.get("x-goog-document-title")
                return b"".join(chunks), title
        except GDocsImportError:
            raise
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Google Docs export failed") from exc
        finally:
            if owns_client:
                await client.aclose()
