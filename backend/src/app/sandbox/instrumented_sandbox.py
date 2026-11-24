"""Observe the outcome of every sandbox run without coupling the adapter to Prometheus."""

from logging import Logger
from time import perf_counter

from src.app.contracts.sandbox.run import SandboxRunRequest, SandboxRunResult
from src.app.exceptions.sandbox import SandboxTimeoutError, SandboxUnavailableError
from src.app.interfaces.observability.metrics_collector import MetricsCollector
from src.app.interfaces.sandbox.sandbox import Sandbox


class InstrumentedSandbox(Sandbox):
    def __init__(self, *, client: Sandbox, logger: Logger, metrics: MetricsCollector) -> None:
        self._client = client
        self._logger = logger
        self._metrics = metrics

    async def run(self, request: SandboxRunRequest) -> SandboxRunResult:
        started = perf_counter()
        outcome = "error"
        try:
            result = await self._client.run(request)
            outcome = "success" if result.ok else "rejected"
            return result
        except SandboxTimeoutError:
            outcome = "timeout"
            raise
        except SandboxUnavailableError:
            outcome = "unavailable"
            raise
        finally:
            duration = perf_counter() - started
            self._metrics.observe_histogram(
                "sandbox_run_duration_seconds",
                duration,
                labels={"outcome": outcome},
                buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 35.0),
            )
            self._logger.info("Sandbox run finished.", extra={"outcome": outcome, "duration_s": round(duration, 3)})

    async def close(self) -> None:
        await self._client.close()
