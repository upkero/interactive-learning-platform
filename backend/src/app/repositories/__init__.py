"""Repositories map ORM rows into immutable contracts.

Every repository method accepts an ``AsyncSession`` and returns only
contracts from ``src.app.contracts``; no ORM models leak outside this
package and no method performs ``commit``/``rollback`` (callers own the
transaction; repositories may call ``flush`` when a generated id is
required).
"""

from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.repositories.primitive_repository import PrimitiveRepository
from src.app.repositories.quiz_attempt_repository import QuizAttemptRepository
from src.app.repositories.report_repository import ReportRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_description_repository import (
    WidgetDescriptionRepository,
)
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_usage_repository import WidgetUsageRepository

__all__ = [
    "DocumentPartRepository",
    "DocumentRepository",
    "GenerationLedgerRepository",
    "ImageRepository",
    "PrimitiveRepository",
    "QuizAttemptRepository",
    "ReportRepository",
    "UserMaterialRepository",
    "UserRepository",
    "WidgetDescriptionRepository",
    "WidgetRepository",
    "WidgetUsageRepository",
]
