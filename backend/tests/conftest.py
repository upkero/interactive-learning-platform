import os

# Дефолтные переменные окружения для запуска тестов
os.environ.setdefault(
    "AUTH_JWT_SECRET", "test-secret-key-must-be-at-least-32-chars-long"
)
os.environ.setdefault(
    "DB_URL", "postgresql+asyncpg://grasp:grasp@localhost:5432/grasp_test"
)
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")