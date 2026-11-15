"""Errors of the quota area."""

from src.app.exceptions.base import BaseAppException


class QuotaError(BaseAppException):
    """Base class of every quota area error."""


class QuotaIntegrityError(QuotaError):
    """Base exception for quota ledger integrity violations."""

    error_code = "quota_integrity_error"
    default_detail = "Quota ledger integrity constraint violated."


class LedgerEntryDuplicateError(QuotaIntegrityError):
    """The (part_id, op) ledger entry already exists (e.g. watchdog race)."""

    status_code = 409
    error_code = "ledger_entry_duplicate"
    default_detail = "A ledger entry for this part and operation already exists."


class QuotaExceededError(QuotaError):
    status_code = 402
    error_code = "quota_exceeded"
    default_detail = "Not enough generation quota."
