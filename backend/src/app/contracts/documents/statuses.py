"""Statuses and roles of the document aggregate as StrEnum with DB-safe values."""

from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    GENERATING = "generating"
    DONE = "done"
    FAILED = "failed"


class SourceType(StrEnum):
    UPLOAD = "upload"
    GDOCS = "gdocs"


class PartStatus(StrEnum):
    QUEUED = "queued"
    MAIN_PASS = "main_pass"
    RESOLVING = "resolving"
    ASSEMBLING = "assembling"
    PUBLISHED = "published"
    FAILED = "failed"


class MaterialRole(StrEnum):
    OWNER = "owner"
    SHARED = "shared"
