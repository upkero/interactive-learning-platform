"""Introspection test: repositories must never return ORM models."""

import inspect
import typing
from collections.abc import Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import src.app.repositories as repositories_package
from src.app.interfaces.repositories.widgets import WidgetDescriptionRepositoryProtocol
from src.app.repositories import (
    DocumentPartRepository,
    DocumentRepository,
    GenerationLedgerRepository,
    ImageRepository,
    PrimitiveRepository,
    QuizAttemptRepository,
    ReportRepository,
    UserMaterialRepository,
    UserRepository,
    WidgetDescriptionRepository,
    WidgetRepository,
    WidgetUsageRepository,
)
from tests.support.fakes.repositories.widgets import FakeWidgetDescriptionRepository

pytestmark = pytest.mark.unit

_ALL_REPOS: list[type[object]] = [
    UserRepository,
    DocumentRepository,
    DocumentPartRepository,
    ImageRepository,
    UserMaterialRepository,
    PrimitiveRepository,
    WidgetRepository,
    WidgetDescriptionRepository,
    WidgetUsageRepository,
    ReportRepository,
    QuizAttemptRepository,
    GenerationLedgerRepository,
]


def _annotation_uses_models(annotation: object) -> bool:
    """True if the annotation type references an ORM model class."""
    if annotation is typing.Any or annotation is type(None):
        return False
    if isinstance(annotation, type):
        return annotation.__module__.startswith("src.app.models")
    return any(_annotation_uses_models(arg) for arg in typing.get_args(annotation))


def _accept_widget_description_repository(repository: WidgetDescriptionRepositoryProtocol) -> None:
    """Type-check every implementation against the public repository contract."""
    del repository


def test_reembedding_lock_is_exposed_by_protocol_and_all_implementations() -> None:
    concrete = WidgetDescriptionRepository(typing.cast(AsyncSession, object()))
    fake = FakeWidgetDescriptionRepository()

    _accept_widget_description_repository(concrete)
    _accept_widget_description_repository(fake)

    assert "lock_for_reembedding" in WidgetDescriptionRepositoryProtocol.__dict__
    assert "lock_for_reembedding" in WidgetDescriptionRepository.__dict__
    assert "lock_for_reembedding" in FakeWidgetDescriptionRepository.__dict__
    assert inspect.iscoroutinefunction(WidgetDescriptionRepositoryProtocol.lock_for_reembedding)
    assert inspect.iscoroutinefunction(concrete.lock_for_reembedding)
    assert inspect.iscoroutinefunction(fake.lock_for_reembedding)
    assert inspect.signature(WidgetDescriptionRepository.lock_for_reembedding) == inspect.signature(
        WidgetDescriptionRepositoryProtocol.lock_for_reembedding
    )
    assert inspect.signature(FakeWidgetDescriptionRepository.lock_for_reembedding) == inspect.signature(
        WidgetDescriptionRepositoryProtocol.lock_for_reembedding
    )


def test_all_repos_exposed_from_package() -> None:
    """The package __init__ must re-export the same set of repositories."""
    for repo in _ALL_REPOS:
        assert getattr(repositories_package, repo.__name__) is repo


def test_public_methods_only_return_contracts_or_primitives() -> None:
    """No public repository method may return models.* types."""
    for repo in _ALL_REPOS:
        for name, member in inspect.getmembers(repo, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            fn = typing.cast(Callable[[], object], member)
            hints = typing.get_type_hints(fn)
            # return annotation of every public method
            return_hint = hints.get("return", None)
            assert not _annotation_uses_models(return_hint), (
                f"{repo.__name__}.{name} returns a model type: {return_hint!r}"
            )
            for arg_name, arg_hint in hints.items():
                assert not _annotation_uses_models(arg_hint), f"{repo.__name__}.{name}[{arg_name}] accepts a model type"
