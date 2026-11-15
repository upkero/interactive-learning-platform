"""A registered user the document was shared with."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SharedUserInfo:
    user_id: UUID
    email: str
    display_name: str | None
    shared_at: datetime
