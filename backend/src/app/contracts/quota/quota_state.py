"""Quota balance and billing period."""

from dataclasses import dataclass

from src.app.contracts.quota.period import QuotaPeriod


@dataclass(frozen=True, slots=True)
class QuotaState:
    monthly_limit: int
    available: int
    period: QuotaPeriod
