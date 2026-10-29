"""All ORM models imported here so Base.metadata contains every table.

Alembic (migrations/env.py) relies on this aggregate import to see
the full metadata for autogeneration and offline scripts.
"""

from src.app.models.base import Base
from src.app.models.document import Document
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.models.image import Image
from src.app.models.primitive import Primitive
from src.app.models.quiz_attempt import QuizAttempt
from src.app.models.report import Report
from src.app.models.user import User
from src.app.models.user_material import UserMaterial
from src.app.models.widget import Widget
from src.app.models.widget_description import WidgetDescription
from src.app.models.widget_usage import WidgetUsage

__all__ = [
    "Base",
    "Document",
    "DocumentPart",
    "GenerationLedger",
    "Image",
    "Primitive",
    "QuizAttempt",
    "Report",
    "User",
    "UserMaterial",
    "Widget",
    "WidgetDescription",
    "WidgetUsage",
]
