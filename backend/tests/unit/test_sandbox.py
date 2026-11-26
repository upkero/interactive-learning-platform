import logging

import httpx
import pytest

from src.app.contracts.sandbox.run import SandboxRunRequest, SandboxRunResult
from src.app.exceptions.sandbox import SandboxTimeoutError, SandboxUnavailableError
from src.app.sandbox.http_sandbox_client import HttpSandboxClient
from src.app.sandbox.instrumented_sandbox import InstrumentedSandbox
from tests.support.fakes.sandbox.sandbox import FakeSandbox

pytestmark = pytest.mark.unit


def request() -> SandboxRunRequest:
    return SandboxRunRequest(source_tsx="export default () => null", param_sets=({},))


def response(ok: bool = True) -> dict[str, object]:
    return {
        "ok": ok,
        "compiled_js": "export default () => null" if ok else None,
        "console_errors": [] if ok else ["compile: failed (line 1)"],
        "screenshots": ["UE5H"] if ok else [],
        "timings": {"total_ms": 5},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("ok", [True, False])
async def test_http_sandbox_result(ok: bool) -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/run"
        assert b'"viewport":{"w":800,"h":500}' in req.content
        return httpx.Response(200, json=response(ok))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://sandbox:3001") as client:
        result = await HttpSandboxClient(client=client).run(request())
    assert result.ok is ok
    assert result.console_errors == (() if ok else ("compile: failed (line 1)",))
    assert result.images[0].data_base64 == "UE5H" if ok else result.images == ()


@pytest.mark.asyncio
async def test_busy_retries_once() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"error": "busy"}) if calls == 1 else httpx.Response(200, json=response())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://sandbox:3001") as client:
        result = await HttpSandboxClient(client=client, busy_retry_seconds=0).run(request())
    assert result.ok
    assert calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [503, 500, 200])
async def test_unavailable_or_bad_response(status: int) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status, json={"error": "bad"}))
    async with httpx.AsyncClient(transport=transport, base_url="http://sandbox:3001") as client:
        with pytest.raises(SandboxUnavailableError):
            await HttpSandboxClient(client=client, busy_retry_seconds=0).run(request())


@pytest.mark.asyncio
async def test_timeout() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://sandbox:3001") as client:
        with pytest.raises(SandboxTimeoutError):
            await HttpSandboxClient(client=client).run(request())


@pytest.mark.asyncio
async def test_network_unavailable() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://sandbox:3001") as client:
        with pytest.raises(SandboxUnavailableError):
            await HttpSandboxClient(client=client).run(request())


class CapturedMetrics:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []

    def observe_histogram(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        assert buckets
        self.calls.append((name, (labels or {})["outcome"], value))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("script", "outcome"),
    [
        (SandboxRunResult(True, "code", (), ("UE5H",), {}), "success"),
        (SandboxRunResult(False, None, ("error",), (), {}), "rejected"),
        (SandboxTimeoutError(), "timeout"),
        (SandboxUnavailableError(), "unavailable"),
    ],
)
async def test_instrumented_outcome(script: SandboxRunResult | Exception, outcome: str) -> None:
    metrics = CapturedMetrics()
    fake = FakeSandbox([script])
    instrumented = InstrumentedSandbox(client=fake, logger=logging.getLogger(__name__), metrics=metrics)  # type: ignore[arg-type]
    if isinstance(script, Exception):
        with pytest.raises(type(script)):
            await instrumented.run(request())
    else:
        assert await instrumented.run(request()) == script
    assert len(metrics.calls) == 1
    assert metrics.calls[0][0:2] == ("sandbox_run_duration_seconds", outcome)
    assert metrics.calls[0][2] >= 0
    await instrumented.close()
    assert fake.closed
