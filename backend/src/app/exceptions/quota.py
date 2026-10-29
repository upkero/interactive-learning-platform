"""Integrity errors of the quota area (mapped from DB IntegrityError)."""

from src.app.exceptions.base import BaseAppException


class QuotaIntegrityError(BaseAppException):
    """Base exception for quota ledger integrity violations."""

    error_code = "quota_integrity_error"
    default_detail = "Quota ledger integrity constraint violated."


class LedgerEntryDuplicateError(QuotaIntegrityError):
    """The (part_id, op) ledger entry already exists (e.g. watchdog race)."""

    status_code = 409
    error_code = "ledger_entry_duplicate"
    default_detail = "A ledger entry for this part and operation already exists."
