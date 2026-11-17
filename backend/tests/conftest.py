import os

import pytest

# Default environment variables for the test run. They are applied only
# when the variable is not already set, so CI keeps full control.
os.environ.setdefault("AUTH_JWT_SECRET", "test-secret-key-must-be-at-least-32-chars-long")
os.environ.setdefault("DB_URL", "postgresql+asyncpg://grasp:grasp@localhost:5432/grasp_test")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")
# SeedSettings has no default password on purpose; tests only need it to load.
os.environ.setdefault("SEED_PASSWORD", "test-seed-password")


@pytest.fixture
def broker_url() -> str:
    """Isolated Redis broker for worker integration tests; never a shared one."""
    broker = os.environ.get("TEST_CELERY_BROKER_URL")
    if not broker:
        if os.environ.get("CI"):
            pytest.fail("TEST_CELERY_BROKER_URL is required in CI")
        pytest.skip("TEST_CELERY_BROKER_URL must point to an isolated Redis broker")
    return broker
