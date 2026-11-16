"""Minimal fake session recording transaction outcomes.

Services open their own session and transaction, so unit tests assert on
``committed``/``rolled_back`` instead of watching explicit calls. Fakes of
the repositories manage their state in memory: they may register their
``rollback``/``checkpoint`` hooks here to emulate the database discarding
the rows of an aborted transaction.
"""

from collections.abc import Callable
from types import TracebackType


class FakeTransaction:
    def __init__(self, session: "FakeSession") -> None:
        self._session = session

    async def __aenter__(self) -> "FakeTransaction":
        self._session.begun += 1
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self._session.committed += 1
            for hook in self._session.commit_hooks:
                hook()
        else:
            self._session.rolled_back += 1
            for hook in self._session.rollback_hooks:
                hook()


class FakeSession:
    def __init__(self) -> None:
        self.begun = 0
        self.committed = 0
        self.rolled_back = 0
        self.commit_hooks: list[Callable[[], None]] = []
        self.rollback_hooks: list[Callable[[], None]] = []

    def on_commit(self, *targets: object) -> None:
        for target in targets:
            hook = getattr(target, "checkpoint", None)
            if callable(hook):
                self.commit_hooks.append(hook)

    def on_rollback(self, *targets: object) -> None:
        for target in targets:
            hook = getattr(target, "rollback", None)
            if callable(hook):
                self.rollback_hooks.append(hook)

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self)
