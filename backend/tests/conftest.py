import os

# Default environment variables for the test run. They are applied only
# when the variable is not already set, so CI keeps full control.
os.environ.setdefault("AUTH_JWT_SECRET", "test-secret-key-must-be-at-least-32-chars-long")
os.environ.setdefault("DB_URL", "postgresql+asyncpg://grasp:grasp@localhost:5432/grasp_test")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
# SeedSettings has no default password on purpose; tests only need it to load.
os.environ.setdefault("SEED_PASSWORD", "test-seed-password")
