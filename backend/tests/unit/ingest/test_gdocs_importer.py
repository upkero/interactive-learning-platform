import httpx
import pytest

from src.app.contracts.documents.statuses import DocumentErrorCode
from src.app.ingest.parsers.gdocs_importer import GDocsImporter, GDocsImportError


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rejects_html_as_private_document() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text="login")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GDocsImportError) as error:
            await GDocsImporter(client=client).fetch("https://docs.google.com/document/d/abc123/edit")
    assert error.value.code is DocumentErrorCode.GDOCS_NOT_PUBLIC


@pytest.mark.asyncio
@pytest.mark.unit
async def test_stops_when_export_is_too_large() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
            content=b"12345",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GDocsImportError):
            await GDocsImporter(client=client, max_bytes=3).fetch("https://docs.google.com/document/d/abc123/edit")
