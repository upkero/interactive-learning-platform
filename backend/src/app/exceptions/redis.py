"""Exceptions of the Redis infrastructure layer."""

from src.app.exceptions.base import BaseAppException


class RedisIsolationConfigurationError(BaseAppException):
    """Two Redis-backed roles were configured to share the same logical database."""

    error_code = "redis_isolation_configuration_error"
    default_detail = "Redis storage roles are not isolated."


__all__ = ["RedisIsolationConfigurationError"]
