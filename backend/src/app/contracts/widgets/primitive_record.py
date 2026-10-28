"""Immutable record of a primitive from the @grasp/primitives catalog."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class PrimitiveRecord:
    id: str
    version: str
    description: str
    modes: list[str]
    params_schema: dict[str, Any]
    updated_at: datetime
