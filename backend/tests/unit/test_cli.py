"""Error reporting of the ``seed-primitives`` management command."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from src import cli
from src.app.core.settings.app import get_app_settings

pytestmark = pytest.mark.unit

BACKEND = Path(__file__).resolve().parents[2]
VALID_CATALOG = BACKEND / "tests" / "support" / "fixtures" / "seed" / "three-frame-catalog.json"


@pytest.fixture
def no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if the command tries to open a database engine."""

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("build_engine must not be called for an invalid catalog")

    monkeypatch.setattr(cli, "build_engine", forbidden)


@pytest.fixture
def fresh_settings() -> Iterator[None]:
    """Re-read settings from the environment and restore the cache afterwards."""
    get_app_settings.cache_clear()
    yield
    get_app_settings.cache_clear()


def _single_stderr_line(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert len(lines) == 1, captured.err
    assert "Traceback" not in captured.err
    return lines[0]


@pytest.mark.usefixtures("no_database")
def test_invalid_catalog_is_one_line_with_exit_code_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    catalog = json.loads(VALID_CATALOG.read_text(encoding="utf-8"))
    del catalog["primitives"][0]["paramsSchema"]
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")

    assert cli.main(["seed-primitives", "--catalog", str(path)]) == 1
    line = _single_stderr_line(capsys)
    assert line.startswith("seed-primitives: Invalid primitives catalog: ")
    assert "primitives.0.paramsSchema: Field required" in line


@pytest.mark.usefixtures("no_database")
def test_invalid_json_is_one_line_with_exit_code_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "catalog.json"
    path.write_text("{not json", encoding="utf-8")

    assert cli.main(["seed-primitives", "--catalog", str(path)]) == 1
    assert _single_stderr_line(capsys).startswith("seed-primitives: Invalid primitives catalog: Invalid JSON")


@pytest.mark.usefixtures("no_database")
def test_missing_catalog_is_one_line_with_exit_code_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "missing.json"

    assert cli.main(["seed-primitives", "--catalog", str(path)]) == 1
    assert _single_stderr_line(capsys) == f"seed-primitives: Primitives catalog not found: {path}"


@pytest.mark.usefixtures("fresh_settings")
def test_settings_errors_are_not_reported_as_catalog_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_POOL_SIZE", "not-a-number")

    with pytest.raises(ValidationError, match="db_pool_size"):
        cli.main(["seed-primitives", "--catalog", str(VALID_CATALOG)])
