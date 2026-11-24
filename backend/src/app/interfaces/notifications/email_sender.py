"""Transport-neutral email sender."""

from typing import Protocol


class EmailSenderProtocol(Protocol):
    async def send(self, *, recipient: str, subject: str, text: str, html: str) -> None: ...
