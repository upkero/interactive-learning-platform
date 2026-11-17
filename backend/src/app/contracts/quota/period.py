"""Billing period with an exclusive end."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class QuotaPeriod:
    start: date
    end: date
