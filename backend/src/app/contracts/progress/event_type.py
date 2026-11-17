"""Event types published to the document progress stream."""

from enum import StrEnum


class ProgressEventType(StrEnum):
    """Closed set of SSE event names from the 1.7 contract."""

    STAGE = "stage"
    PART_STATUS = "part_status"
    PART_READY = "part_ready"
    DOCUMENT_DONE = "document_done"
    ERROR = "error"
