"""Checks of all quiz types and persistence of attempts."""

from dataclasses import replace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import MaterialRole, PartDraft, PartStatus
from src.app.exceptions.quizzes import InvalidQuizAnswerError
from src.app.services.documents.quiz_check_service import QuizCheckService
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.documents import FakeDocumentPartRepository, FakeUserMaterialRepository
from tests.support.fakes.repositories.quizzes import FakeQuizAttemptRepository

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("kind", "correct", "valid", "invalid"),
    [
        ("single_choice", 1, 1, 2),
        ("multiple_choice", [1, 2], [2, 1], [1]),
        ("ordering", [1, 2], [1, 2], [2, 1]),
        ("numeric", 1.0, 1.05, 1.2),
    ],
)
async def test_check_four_types_and_record_every_attempt(kind: str, correct: Any, valid: Any, invalid: Any) -> None:
    user, document_id = uuid4(), uuid4()
    parts, materials, attempts = FakeDocumentPartRepository(), FakeUserMaterialRepository(), FakeQuizAttemptRepository()
    await materials.create(user_id=user, document_id=document_id, role=MaterialRole.OWNER)
    (part,) = await parts.add_many(
        document_id, [PartDraft(index=0, title="Page", topic_ids=[], source_markdown="x", token_count=1)]
    )
    parts._parts[part.id] = replace(
        part,
        status=PartStatus.PUBLISHED,
        content={
            "quizzes": [
                {
                    "quiz_key": "q",
                    "type": kind,
                    "correct_answer": correct,
                    "tolerance": 0.1,
                    "explanation": "because",
                    "option_explanations": ["why"],
                }
            ]
        },
    )
    session = FakeSession()
    factory = cast(async_sessionmaker[AsyncSession], lambda: session)
    service = QuizCheckService(
        session_factory=factory,
        parts=lambda _: parts,
        materials=lambda _: materials,
        attempts=lambda _: attempts,
    )
    first = await service.check(user_id=user, part_id=part.id, quiz_key="q", answer=valid)
    second = await service.check(user_id=user, part_id=part.id, quiz_key="q", answer=invalid)
    assert first.is_correct is True and second.is_correct is False
    assert first.correct_answer == correct
    assert first.explanation == "because"
    assert len(await attempts.list_by_part(part.id)) == 2
    assert session.committed == 2
    with pytest.raises(InvalidQuizAnswerError):
        await service.check(user_id=user, part_id=part.id, quiz_key="q", answer={})
