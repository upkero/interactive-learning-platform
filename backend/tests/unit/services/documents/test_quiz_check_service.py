"""Checks of all quiz types and persistence of attempts."""

import json
from dataclasses import replace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import MaterialRole, PartDraft, PartStatus
from src.app.core.fixtures import PUBLISHED_PART_FIXTURE
from src.app.exceptions.quizzes import InvalidQuizAnswerError, QuizIntegrityError
from src.app.services.documents.quiz_check_service import QuizCheckService, check_answer
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.documents import FakeDocumentPartRepository, FakeUserMaterialRepository
from tests.support.fakes.repositories.quizzes import FakeQuizAttemptRepository

pytestmark = pytest.mark.unit


def test_seed_quiz_uses_separate_answer_key() -> None:
    fixture = PUBLISHED_PART_FIXTURE
    content = json.loads(fixture.read_text())["content"]
    quiz = content["quizzes"][0]
    key = content["answer_keys"][quiz["key"]]
    assert check_answer(quiz, key, "a").is_correct
    assert not check_answer(quiz, key, "b").is_correct


@pytest.mark.parametrize(
    ("quiz", "key", "answer"),
    [
        ({"type": "numeric"}, {}, 1.0),
        ({"type": "numeric"}, {"answer": 1.0, "tolerance": -1}, 1.0),
        ({"type": "single_choice"}, {"correct_id": "a", "why_wrong": {"b": 42}}, "a"),
    ],
)
def test_malformed_answer_key_is_not_exposed(quiz: dict[str, object], key: dict[str, object], answer: object) -> None:
    with pytest.raises(QuizIntegrityError):
        check_answer(quiz, key, answer)


@pytest.mark.parametrize(
    ("kind", "correct", "valid", "invalid"),
    [
        ("single_choice", "a", "a", "b"),
        ("multiple_choice", ["a", "b"], ["b", "a"], ["a"]),
        ("ordering", ["a", "b"], ["a", "b"], ["b", "a"]),
        ("numeric", 1.0, 1.05, 1.2),
    ],
)
async def test_check_four_types_and_record_every_attempt(kind: str, correct: Any, valid: Any, invalid: Any) -> None:
    user, document_id = uuid4(), uuid4()
    parts, materials, attempts = FakeDocumentPartRepository(), FakeUserMaterialRepository(), FakeQuizAttemptRepository()
    await materials.create(user_id=user, document_id=document_id, role=MaterialRole.OWNER)
    (part,) = await parts.add_many(
        document_id,
        [PartDraft(index=0, title="Page", topic_ids=[], source_markdown="x", token_count=1, quota_period_start=None)],
    )
    parts._parts[part.id] = replace(
        part,
        status=PartStatus.PUBLISHED,
        content={
            "quizzes": [{"key": "q", "type": kind}],
            "answer_keys": {
                "q": {
                    {
                        "single_choice": "correct_id",
                        "multiple_choice": "correct_ids",
                        "ordering": "correct_order",
                        "numeric": "answer",
                    }[kind]: correct,
                    "tolerance": 0.1,
                    "explanation": "because",
                    "why_wrong": {"a": "why"},
                    "common_mistakes": ["why"],
                }
            },
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
