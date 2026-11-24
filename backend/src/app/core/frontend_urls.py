"""Public links for notification templates."""

from uuid import UUID


def material_url(document_id: UUID, locale: str, public_app_url: str) -> str:
    return f"{public_app_url.rstrip('/')}/{locale}/documents/{document_id}"


def profile_url(locale: str, public_app_url: str) -> str:
    return f"{public_app_url.rstrip('/')}/{locale}/profile"
