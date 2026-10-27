"""Introspection test: repositories must never return ORM models."""

import inspect
import typing
from collections.abc import Callable

import pytest

import src.app.repositories as repositories_package
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


def _model_module_names() -> set[str]:

    # Every ORM class lives in src.app.models (or src.app.models.*)
    return {"src.app.models", "src.app.models.base"}


def _annotation_uses_models(annotation: object) -> bool:
    """True if the annotation type references an ORM model class."""
    if annotation is typing.Any or annotation is type(None):
        return False
    if isinstance(annotation, type):
        return annotation.__module__ in _model_module_names()
    return any(_annotation_uses_models(arg) for arg in typing.get_args(annotation))


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
