from abc import ABC, abstractmethod

from src.app.contracts.sandbox.run import SandboxRunRequest, SandboxRunResult


class Sandbox(ABC):
    @abstractmethod
    async def run(self, request: SandboxRunRequest) -> SandboxRunResult: ...

    @abstractmethod
    async def close(self) -> None: ...
