"""Reference inputs and answers of the main-pass tests (story 2.2)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from src.app.contracts.documents.topic_node import TopicNode, topic_roots
from src.app.contracts.solver.main_pass import MainPassInput, PartImage, ReaderProfile
from src.app.contracts.widgets import PrimitiveRecord

_DIR = Path(__file__).resolve().parent
SNAPSHOT_DIR = _DIR / "snapshots"

DOCUMENT_ID = UUID("6a0f0e3c-1f0b-4d3a-9d3e-0a0b0c0d0e01")
PART_ID = UUID("6a0f0e3c-1f0b-4d3a-9d3e-0a0b0c0d0e02")
PART_ID_ACTIVATION = UUID("6a0f0e3c-1f0b-4d3a-9d3e-0a0b0c0d0e03")
PRIMITIVE_UPDATED_AT = datetime(2026, 1, 1, tzinfo=UTC)

_PART_IDS = {"neurons": PART_ID, "activation": PART_ID_ACTIVATION}


def load_json(name: str) -> Any:
    return json.loads((_DIR / name).read_text(encoding="utf-8"))


def load_text(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8")


def build_document() -> dict[str, Any]:
    return cast(dict[str, Any], load_json("document.json"))


def build_outline() -> tuple[TopicNode, ...]:
    outline: list[dict[str, Any]] = build_document()["outline"]
    return topic_roots(outline)


def build_part(part_key: str = "neurons") -> dict[str, Any]:
    for part in build_document()["parts"]:
        if part["key"] == part_key:
            return cast(dict[str, Any], part)
    raise KeyError(part_key)


def build_images(part_key: str = "neurons") -> tuple[PartImage, ...]:
    return tuple(
        PartImage(
            id=UUID(row["id"]),
            alias=row["alias"],
            caption=row["caption"],
            description=row["description"],
        )
        for row in build_part(part_key)["images"]
    )


def build_input(part_key: str = "neurons") -> MainPassInput:
    document = build_document()
    part = build_part(part_key)
    return MainPassInput(
        document_id=DOCUMENT_ID,
        part_id=_PART_IDS[part_key],
        document_title=document["title"],
        outline=build_outline(),
        part_title=part["title"],
        part_markdown=load_text(part["markdown"]),
        part_topics=tuple(part["topics"]),
        profile=ReaderProfile.from_mapping(document["profile"]),
        images=build_images(part_key),
    )


def build_page_draft(name: str = "page_draft.json") -> dict[str, Any]:
    draft: dict[str, Any] = load_json(name)
    return draft


def build_injections() -> list[dict[str, str]]:
    injections: list[dict[str, str]] = load_json("injections.json")
    return injections


def build_primitives() -> list[PrimitiveRecord]:
    rows: list[dict[str, Any]] = load_json("primitives.json")
    return [
        PrimitiveRecord(
            id=row["id"],
            version=row["version"],
            description=row["description"],
            modes=list(row["modes"]),
            params_schema={},
            updated_at=PRIMITIVE_UPDATED_AT,
        )
        for row in rows
    ]


def load_snapshot(name: str) -> str:
    return (SNAPSHOT_DIR / name).read_text(encoding="utf-8")


__all__ = [
    "DOCUMENT_ID",
    "PART_ID",
    "PART_ID_ACTIVATION",
    "SNAPSHOT_DIR",
    "build_document",
    "build_images",
    "build_injections",
    "build_input",
    "build_outline",
    "build_page_draft",
    "build_part",
    "build_primitives",
    "load_json",
    "load_snapshot",
    "load_text",
]
