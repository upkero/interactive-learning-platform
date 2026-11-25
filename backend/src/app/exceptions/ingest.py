"""Domain errors while importing or parsing documents."""

from src.app.contracts.documents.statuses import DocumentErrorCode


class ParseError(Exception):
    """The source could not be converted to Markdown."""


class IngestFailure(Exception):
    """A known ingestion failure with a public error code."""

    def __init__(self, code: DocumentErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class GDocsImportError(IngestFailure):
    """The Google Docs export could not be retrieved."""
