from collections.abc import Sequence

from src.app.contracts.sandbox.run import SandboxRunRequest, SandboxRunResult
from src.app.interfaces.sandbox.sandbox import Sandbox


class FakeSandbox(Sandbox):
    """Scripted responses; unexpected calls fail instead of silently succeeding."""

    def __init__(self, results: Sequence[SandboxRunResult | Exception]) -> None:
        self.results = list(results)
        self.requests: list[SandboxRunRequest] = []
        self.closed = False

    async def run(self, request: SandboxRunRequest) -> SandboxRunResult:
        self.requests.append(request)
        if not self.results:
            raise AssertionError("FakeSandbox: no result scripted")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def close(self) -> None:
        self.closed = True
