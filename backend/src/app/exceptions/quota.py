"""Integrity errors of the quota area (mapped from DB IntegrityError)."""

from src.app.exceptions.base import BaseAppException


class QuotaIntegrityError(BaseAppException):
    """Quota ledger integrity violation, e.g. a duplicate refund for a part."""

    status_code = 409
    error_code = "quota_integrity_error"
    default_detail = "Quota ledger integrity constraint violated."
