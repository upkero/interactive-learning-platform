"""Best-effort, idempotent document completion emails."""

import logging
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import TERMINAL_DOCUMENT_STATUSES, PartStatus
from src.app.core.frontend_urls import material_url, profile_url
from src.app.core.settings.app import AppSettings
from src.app.core.settings.smtp import SMTPSettings
from src.app.interfaces.notifications.claims import NotificationClaims
from src.app.interfaces.notifications.email_sender import EmailSenderProtocol
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, DocumentRepositoryProtocol
from src.app.interfaces.repositories.users import UserRepositoryProtocol

logger = logging.getLogger(__name__)
_templates = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=True),
)


class NotificationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        users: Callable[[AsyncSession], UserRepositoryProtocol],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        claims: NotificationClaims,
        sender: EmailSenderProtocol,
        app_settings: AppSettings,
        smtp_settings: SMTPSettings,
    ) -> None:
        self._session_factory = session_factory
        self._users = users
        self._documents = documents
        self._parts = parts
        self._claims = claims
        self._sender = sender
        self._app_settings = app_settings
        self._smtp_settings = smtp_settings

    async def on_document_finished(self, document_id: UUID) -> None:
        """Never change a part's result because mail, Redis or a read failed."""
        if not self._smtp_settings.enabled:
            logger.info("notification.email_disabled", extra={"document_id": str(document_id)})
            return
        try:
            async with self._session_factory() as session:
                document = await self._documents(session).get(document_id)
                if document is None or document.status not in TERMINAL_DOCUMENT_STATUSES:
                    return
                user = await self._users(session).get(document.owner_id)
                if user is None or not user.notify_email:
                    return
                parts = await self._parts(session).list_by_document(document_id)
        except Exception:
            logger.warning("notification.data_unavailable", extra={"document_id": str(document_id)}, exc_info=True)
            return
        claim: str | None = None
        try:
            current = [part for part in parts if part.index >= document.generation_start_index]
            ready = sum(part.status is PartStatus.PUBLISHED for part in current)
            total = len(current)
            outcome = "failed" if not ready else "partial" if ready < total else "ready"
            language = user.locale if user.locale in ("ru", "en") else "en"
            context = {
                "title": document.title,
                "ready": ready,
                "total": total,
                "outcome": outcome,
                "material_url": material_url(document_id, language, self._app_settings.public_app_url),
                "profile_url": profile_url(language, self._app_settings.public_app_url),
            }
            claim = await self._claims.claim(document_id, self._smtp_settings.notification_ttl_seconds)
            if claim is None:
                return
            await self._sender.send(
                recipient=user.email,
                subject=_templates.get_template(f"{language}/subject.txt").render(**context).strip(),
                text=_templates.get_template(f"{language}/document_done.txt").render(**context).strip(),
                html=_templates.get_template(f"{language}/document_done.html").render(**context).strip(),
            )
        except Exception:
            logger.warning("notification.email_failed", extra={"document_id": str(document_id)}, exc_info=True)
            if claim is not None:
                try:
                    await self._claims.release(document_id, claim)
                except Exception:
                    logger.warning(
                        "notification.claim_release_failed", extra={"document_id": str(document_id)}, exc_info=True
                    )
