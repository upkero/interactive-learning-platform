import asyncio

import httpx

from src.app.contracts.sandbox.run import SandboxRunRequest, SandboxRunResult
from src.app.exceptions.sandbox import SandboxTimeoutError, SandboxUnavailableError
from src.app.interfaces.sandbox.sandbox import Sandbox


class HttpSandboxClient(Sandbox):
    def __init__(self, *, client: httpx.AsyncClient, busy_retry_seconds: float = 2.0) -> None:
        self._client = client
        self._busy_retry_seconds = busy_retry_seconds

    async def run(self, request: SandboxRunRequest) -> SandboxRunResult:
        payload = {
            "source_tsx": request.source_tsx,
            "param_sets": list(request.param_sets),
            "mode": request.mode,
            "labels": request.labels or {},
            "locale": request.locale,
            "viewport": {"w": request.viewport_width, "h": request.viewport_height},
        }
        try:
            response = await self._client.post("/run", json=payload)
            if response.status_code == 503:
                await asyncio.sleep(self._busy_retry_seconds)
                response = await self._client.post("/run", json=payload)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
                raise ValueError("Invalid sandbox response")
            return SandboxRunResult(
                ok=data["ok"],
                compiled_js=data.get("compiled_js"),
                console_errors=tuple(data["console_errors"]),
                screenshots_png_base64=tuple(data["screenshots"]),
                timings=dict(data["timings"]),
            )
        except httpx.TimeoutException as exc:
            raise SandboxTimeoutError() from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise SandboxUnavailableError() from exc

    async def close(self) -> None:
        await self._client.aclose()
