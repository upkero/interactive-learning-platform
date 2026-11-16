"""Exercise document diagnostics migration on the isolated test database."""

import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

_BACKEND = Path(__file__).resolve().parents[3]


def _migrate(target: str, *, downgrade: bool = False) -> None:
    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "migrations"))
    (command.downgrade if downgrade else command.upgrade)(cfg, target)


async def test_document_diagnostics_migration_preserves_legacy_text(db: AsyncEngine) -> None:
    owner, old_document, coded_document = uuid4(), uuid4(), uuid4()
    await asyncio.to_thread(_migrate, "0002_report_comments", downgrade=True)
    try:
        async with db.begin() as connection:
            await connection.execute(
                text("INSERT INTO users (id, email, password_hash) VALUES (:id, :email, 'hash')"),
                {"id": owner, "email": f"migration-{owner}@example.com"},
            )
            for document_id, error in (
                (old_document, "parser crashed: secret detail"),
                (coded_document, "parse_failed"),
            ):
                await connection.execute(
                    text(
                        "INSERT INTO documents (id, owner_id, title, source_type, object_key, mime_type, "
                        "size_bytes, checksum, status, error) VALUES "
                        "(:id, :owner, 'test', 'upload', 'source', 'text/plain', 1, :checksum, 'failed', :error)"
                    ),
                    {"id": document_id, "owner": owner, "checksum": "a" * 64, "error": error},
                )
        await asyncio.to_thread(_migrate, "head")
        async with db.connect() as connection:
            rows = (await connection.execute(text("SELECT id, error_code, error_detail FROM documents"))).all()
        results = {row.id: (row.error_code, row.error_detail) for row in rows}
        assert results[old_document] == ("parse_failed", "parser crashed: secret detail")
        assert results[coded_document] == ("parse_failed", None)
        async with db.begin() as connection:
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.columns "
                        "WHERE table_name = 'document_parts' AND column_name = 'error'"
                    )
                )
                == 1
            )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text("UPDATE documents SET error_code = 'not_a_public_code' WHERE id = :id"),
                        {"id": old_document},
                    )

        await asyncio.to_thread(_migrate, "0002_report_comments", downgrade=True)
        async with db.connect() as connection:
            errors: dict[UUID, str | None] = dict(
                (await connection.execute(text("SELECT id, error FROM documents"))).all()
            )
        assert errors[old_document] == "parser crashed: secret detail"
        assert errors[coded_document] == "parse_failed"
    finally:
        await asyncio.to_thread(_migrate, "head")
