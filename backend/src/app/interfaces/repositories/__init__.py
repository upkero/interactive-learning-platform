"""Protocols of the repository layer.

Real repositories (``src.app.repositories``) and their in-memory fakes
(``tests.support.fakes.repositories``) both conform to these protocols;
mypy strict verifies the two never drift apart (story 1.2.7).
"""

from src.app.interfaces.repositories.documents import (
    DocumentPartRepositoryProtocol,
    DocumentRepositoryProtocol,
    ImageRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.repositories.quizzes import QuizAttemptRepositoryProtocol
from src.app.interfaces.repositories.quota import GenerationLedgerRepositoryProtocol
from src.app.interfaces.repositories.users import UserRepositoryProtocol
from src.app.interfaces.repositories.widgets import (
    PrimitiveRepositoryProtocol,
    ReportRepositoryProtocol,
    WidgetDescriptionRepositoryProtocol,
    WidgetRepositoryProtocol,
    WidgetUsageRepositoryProtocol,
)

__all__ = [
    "DocumentPartRepositoryProtocol",
    "DocumentRepositoryProtocol",
    "GenerationLedgerRepositoryProtocol",
    "ImageRepositoryProtocol",
    "PrimitiveRepositoryProtocol",
    "QuizAttemptRepositoryProtocol",
    "ReportRepositoryProtocol",
    "UserMaterialRepositoryProtocol",
    "UserRepositoryProtocol",
    "WidgetDescriptionRepositoryProtocol",
    "WidgetRepositoryProtocol",
    "WidgetUsageRepositoryProtocol",
]
