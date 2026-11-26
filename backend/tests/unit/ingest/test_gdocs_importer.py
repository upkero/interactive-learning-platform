from collections.abc import AsyncIterator

import anyio
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
            await GDocsImporter(client=client, max_bytes=1024).fetch("https://docs.google.com/document/d/abc123/edit")
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


@pytest.mark.asyncio
@pytest.mark.unit
async def test_export_follows_only_allowed_redirects() -> None:
    visited: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        visited.append(request.url.host)
        if request.url.host == "docs.google.com":
            return httpx.Response(302, headers={"location": "https://download.googleusercontent.com/file"})
        return httpx.Response(200, content=b"docx")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        result = await GDocsImporter(client=client, max_bytes=1024).fetch(
            "https://docs.google.com/document/d/abc123/edit"
        )
    assert result == (b"docx", None)
    assert visited == ["docs.google.com", "download.googleusercontent.com"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_export_blocks_redirect_to_private_network() -> None:
    visited: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        visited.append(request.url.host)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        with pytest.raises(GDocsImportError):
            await GDocsImporter(client=client, max_bytes=1024).fetch("https://docs.google.com/document/d/abc123/edit")
    assert visited == ["docs.google.com"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_export_translates_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GDocsImportError) as error:
            await GDocsImporter(client=client, max_bytes=1024).fetch("https://docs.google.com/document/d/abc123/edit")
    assert error.value.code is DocumentErrorCode.GDOCS_IMPORT_FAILED


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_limit_without_content_length() -> None:
    class Chunks(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"123"
            yield b"456"

    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Chunks()))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(GDocsImportError, match="too large"):
            await GDocsImporter(client=client, max_bytes=5).fetch("https://docs.google.com/document/d/abc123/edit")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_total_deadline_rejects_slow_stream_even_when_each_read_completes() -> None:
    class Drip(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            while True:
                await anyio.sleep(0.02)
                yield b"x"

    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Drip()))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(GDocsImportError) as error:
            await GDocsImporter(client=client, max_bytes=1024, timeout_seconds=0.05).fetch(
                "https://docs.google.com/document/d/abc123/edit"
            )
    assert error.value.code is DocumentErrorCode.GDOCS_IMPORT_FAILED
