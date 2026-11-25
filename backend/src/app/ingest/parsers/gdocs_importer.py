from email.message import Message

import anyio
import httpx

from src.app.contracts.documents.statuses import DocumentErrorCode
from src.app.exceptions.ingest import GDocsImportError as GDocsImportError
from src.app.ingest.gdocs_url import gdocs_id


class GDocsImporter:
    """Download a public Google Docs export within one size and time budget."""

    def __init__(
        self, *, max_bytes: int, client: httpx.AsyncClient | None = None, timeout_seconds: float = 30.0
    ) -> None:
        self._max_bytes = max_bytes
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def fetch(self, url: str) -> tuple[bytes, str | None]:
        """Export a public document; malformed worker URLs are import failures."""
        document_id = gdocs_id(url)
        if document_id is None:
            raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Invalid Google Docs URL")
        export_url = f"https://docs.google.com/document/d/{document_id}/export?format=docx"
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            with anyio.fail_after(self._timeout_seconds):
                return await self._download(client, export_url)
        except GDocsImportError:
            raise
        except (TimeoutError, httpx.HTTPError) as exc:
            raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Google Docs export failed") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def _download(self, client: httpx.AsyncClient, export_url: str) -> tuple[bytes, str | None]:
        url = httpx.URL(export_url)
        for _ in range(10):
            allowed = url.host == "docs.google.com" or url.host.endswith(".googleusercontent.com")
            if url.scheme != "https" or not allowed:
                raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Invalid Google Docs redirect")
            async with client.stream("GET", url, follow_redirects=False) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Invalid Google Docs redirect")
                    url = url.join(location)
                    continue
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" in content_type:
                    raise GDocsImportError(DocumentErrorCode.GDOCS_NOT_PUBLIC, "Google Docs document is not public")
                if response.status_code >= 400:
                    raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Google Docs export failed")
                try:
                    length = int(response.headers.get("content-length", "0") or 0)
                except ValueError as exc:
                    raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Invalid export size") from exc
                if length > self._max_bytes:
                    raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Google Docs export is too large")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self._max_bytes:
                        raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Google Docs export is too large")
                    chunks.append(chunk)
                disposition = Message()
                disposition["content-disposition"] = response.headers.get("content-disposition", "")
                title = disposition.get_filename()
                return b"".join(chunks), title
        raise GDocsImportError(DocumentErrorCode.GDOCS_IMPORT_FAILED, "Too many Google Docs redirects")
