"""SMTP delivery for rendered notification messages."""

from email.message import EmailMessage

import aiosmtplib

from src.app.core.settings.smtp import SMTPSettings


class EmailSender:
    def __init__(self, settings: SMTPSettings) -> None:
        self._settings = settings

    async def send(self, *, recipient: str, subject: str, text: str, html: str) -> None:
        message = EmailMessage()
        message["From"] = self._settings.from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        await aiosmtplib.send(
            message,
            hostname=self._settings.host,
            port=self._settings.port,
            username=self._settings.username or None,
            password=self._settings.password or None,
            use_tls=self._settings.use_tls,
            start_tls=self._settings.start_tls,
            timeout=self._settings.timeout,
        )
