"""Fields explicitly provided for a profile update."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ProfileUpdate:
    provided: frozenset[str]
    display_name: str | None = None
    locale: Literal["ru", "en"] | None = None
    notify_email: bool | None = None
