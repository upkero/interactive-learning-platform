"""Error reporting of the ``seed-primitives`` management command."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import RedisDsn, ValidationError

from src import cli
from src.app.core.settings.app import get_app_settings
from src.app.core.settings.celery import CelerySettings
from src.app.core.settings.embeddings import EmbeddingsSettings
from src.app.core.settings.progress import ProgressSettings
from src.app.core.settings.rate_limit import RateLimitSettings
from src.app.exceptions.redis import RedisIsolationConfigurationError

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


@pytest.mark.usefixtures("no_database")
def test_non_utf8_catalog_is_reported_as_invalid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "catalog.json"
    path.write_bytes(b"\xff\xfe{}")

    assert cli.main(["seed-primitives", "--catalog", str(path)]) == 1
    assert _single_stderr_line(capsys).startswith("seed-primitives: Invalid primitives catalog: Invalid JSON")


@pytest.mark.usefixtures("no_database")
def test_unreadable_catalog_is_one_line_with_exit_code_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "catalog.json"
    path.write_text("{}", encoding="utf-8")

    def denied(self: Path) -> bytes:
        raise PermissionError(13, "Permission denied", str(self))

    # chmod is not enough: the test may run as root, which reads any file.
    monkeypatch.setattr(Path, "read_bytes", denied)

    assert cli.main(["seed-primitives", "--catalog", str(path)]) == 1
    assert _single_stderr_line(capsys) == f"seed-primitives: [Errno 13] Permission denied: '{path}'"


@pytest.mark.usefixtures("fresh_settings")
def test_settings_errors_are_not_reported_as_catalog_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_POOL_SIZE", "not-a-number")

    with pytest.raises(ValidationError, match="db_pool_size"):
        cli.main(["seed-primitives", "--catalog", str(VALID_CATALOG)])


def test_reembed_descriptions_command_is_registered() -> None:
    """The re-embedding command is parsed without touching the database."""
    args = cli.build_parser().parse_args(["reembed-descriptions"])

    assert args.command == "reembed-descriptions"


@pytest.mark.parametrize(
    ("colliding_role", "expected_setting"),
    [
        ("broker", "CELERY_BROKER_URL"),
        ("progress", "REDIS_PROGRESS_URL"),
        ("rate", "RATE_LIMIT_STORAGE_URI"),
    ],
)
async def test_reembed_descriptions_rejects_shared_redis_database_before_opening_database(
    colliding_role: str,
    expected_setting: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("build_engine must not be called for unsafe Redis isolation")

    broker_url = "redis://localhost:6379/0"
    progress_url = "redis://localhost:6379/1"
    rate_limit_uri = "redis://localhost:6379/2"
    if colliding_role == "broker":
        broker_url = "redis://localhost:6379/3"
    elif colliding_role == "progress":
        progress_url = "redis://localhost:6379/3"
    else:
        assert colliding_role == "rate"
        rate_limit_uri = "redis://localhost:6379/3"

    monkeypatch.setattr(cli, "build_engine", forbidden)
    monkeypatch.setattr(
        cli,
        "get_embeddings_settings",
        lambda: EmbeddingsSettings(cache_redis_url="redis://localhost:6379/3", _env_file=None),
    )
    monkeypatch.setattr(
        cli,
        "get_celery_settings",
        lambda: CelerySettings(broker_url=broker_url, _env_file=None),
    )
    monkeypatch.setattr(
        cli,
        "get_progress_settings",
        lambda: ProgressSettings(url=RedisDsn(progress_url), _env_file=None),
    )
    monkeypatch.setattr(
        cli,
        "get_rate_limit_settings",
        lambda: RateLimitSettings(storage_uri=rate_limit_uri, _env_file=None),
    )

    with pytest.raises(RedisIsolationConfigurationError, match="same Redis logical database") as error:
        await cli._run_reembed_descriptions()

    assert expected_setting in str(error.value)
