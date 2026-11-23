"""Recording email sender with injectable delivery failure."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SentEmail:
    recipient: str
    subject: str
    text: str
    html: str


class FakeEmailSender:
    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[SentEmail] = []
        self.error = error

    async def send(self, *, recipient: str, subject: str, text: str, html: str) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append(SentEmail(recipient, subject, text, html))
