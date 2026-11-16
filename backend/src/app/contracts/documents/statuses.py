"""Statuses and roles of the document aggregate as StrEnum with DB-safe values."""

from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    GENERATING = "generating"
    DONE = "done"
    FAILED = "failed"


class DocumentErrorCode(StrEnum):
    """Why a document ended up in ``failed`` (story 1.9, migration 0003).

    Only the code is exposed: the client translates it through its
    ``errors.<code>`` dictionary, while technical details (exception
    text) stay in server-side diagnostics and never leave the API.
    """

    PARSE_FAILED = "parse_failed"
    GDOCS_NOT_PUBLIC = "gdocs_not_public"
    GDOCS_IMPORT_FAILED = "gdocs_import_failed"
    TOO_MANY_PAGES = "too_many_pages"
    EMPTY_DOCUMENT = "empty_document"
    ENQUEUE_FAILED = "enqueue_failed"


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


ACTIVE_PART_STATUSES = frozenset({PartStatus.MAIN_PASS, PartStatus.RESOLVING, PartStatus.ASSEMBLING})


class MaterialRole(StrEnum):
    OWNER = "owner"
    SHARED = "shared"
