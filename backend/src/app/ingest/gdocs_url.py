"""Validation shared by the HTTP import and the worker."""

import re

_GDOCS_URL_RE = re.compile(
    r"^https://docs\.google\.com/document/(?:u/\d+/)?d/(?!e/)([A-Za-z0-9][A-Za-z0-9_-]*)(?:/[^?\s]*)?(?:\?[^\s]*)?$"
)


def gdocs_id(url: str) -> str | None:
    """Extract a document ID, excluding published-page export tokens."""
    match = _GDOCS_URL_RE.fullmatch(url.strip())
    return match.group(1) if match else None
