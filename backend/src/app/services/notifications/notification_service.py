"""Idempotent document completion email notifications."""

import logging
from collections.abc import Callable
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.core.settings.app import AppSettings
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, DocumentRepositoryProtocol
from src.app.interfaces.repositories.users import UserRepositoryProtocol
from src.app.services.notifications.email_sender import EmailSender

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        users: Callable[[AsyncSession], UserRepositoryProtocol],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        redis: Redis,
        sender: EmailSender,
        app_settings: AppSettings,
    ) -> None:
        self._session_factory = session_factory
        self._users = users
        self._documents = documents
        self._parts = parts
        self._redis = redis
        self._sender = sender
        self._app_settings = app_settings

    async def on_document_finished(self, document_id: UUID) -> None:
        claimed = await self._redis.set(f"notified:{document_id}", "1", nx=True, ex=7 * 24 * 3600)
        if not claimed:
            return
        try:
            async with self._session_factory() as session:
                document = await self._documents(session).get(document_id)
                if document is None:
                    return
                user = await self._users(session).get(document.owner_id)
                if user is None or not user.notify_email:
                    return
                parts = await self._parts(session).list_by_document(document_id)
            count = sum(part.status.value == "published" for part in parts)
            language = user.locale if user.locale in ("ru", "en") else "en"
            subject = "Материал готов" if language == "ru" else "Your material is ready"
            title = _escape(document.title)
            link = f"{self._app_settings.public_app_url}/materials/{document.id}"
            text = _render_text(language, document.title, count, link)
            html = _render_html(language, title, count, link)
            await self._sender.send(recipient=user.email, subject=subject, text=text, html=html)
        except Exception:
            logger.warning(
                "Document completion email was not sent.",
                extra={"document_id": str(document_id)},
                exc_info=True,
            )

    async def on_document_finished_for_part(self, part_id: UUID) -> None:
        async with self._session_factory() as session:
            part = await self._parts(session).get(part_id)
            if part is None:
                return
            document = await self._documents(session).get(part.document_id)
        if document is not None and document.status.value in ("done", "failed"):
            await self.on_document_finished(document.id)


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_text(locale: str, title: str, count: int, link: str) -> str:
    if locale == "ru":
        return (
            f"Материал «{title}» готов. Готовых частей: {count}.\n"
            f"Открыть: {link}\n\nОтключить уведомления: {link}/profile"  # noqa: RUF001
        )
    return (
        f'Your material "{title}" is ready. Ready parts: {count}.\n'
        f"Open: {link}\n\nDisable notifications: {link}/profile"
    )


def _render_html(locale: str, title: str, count: int, link: str) -> str:
    if locale == "ru":
        return (
            f"<p>Материал «{title}» готов.</p><p>Готовых частей: {count}.</p>"
            f'<p><a href="{link}">Открыть материал</a></p>'
            f'<p><a href="{link}/profile">Отключить уведомления</a></p>'
        )
    return (
        f'<p>Your material "{title}" is ready.</p><p>Ready parts: {count}.</p>'
        f'<p><a href="{link}">Open material</a></p>'
        f'<p><a href="{link}/profile">Disable notifications</a></p>'
    )
