from src.app.exceptions.base import BaseAppException


class SandboxUnavailableError(BaseAppException):
    error_code = "sandbox_unavailable"
    default_detail = "Sandbox is unavailable."


class SandboxTimeoutError(SandboxUnavailableError):
    error_code = "sandbox_timeout"
    default_detail = "Sandbox request timed out."
