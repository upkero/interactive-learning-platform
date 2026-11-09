"""CLI behavior for management commands."""

from unittest.mock import AsyncMock, patch

from src.cli import main


def test_seed_primitives_handles_missing_catalog(capsys) -> None:
    with patch(
        "src.cli._run_seed_primitives",
        new=AsyncMock(side_effect=FileNotFoundError("Primitives catalog not found: /tmp/missing.json")),
    ):
        assert main(["seed-primitives", "--catalog", "/tmp/missing.json"]) == 2
    stderr = capsys.readouterr().err.strip()
    assert stderr == "seed-primitives: Primitives catalog not found: /tmp/missing.json"
    assert "Traceback" not in stderr


def test_seed_primitives_handles_invalid_catalog(capsys) -> None:
    with patch(
        "src.cli._run_seed_primitives",
        new=AsyncMock(side_effect=ValueError("Invalid primitives catalog: primitives.0.paramsSchema: Field required")),
    ):
        assert main(["seed-primitives", "--catalog", "/tmp/catalog.json"]) == 2
    stderr = capsys.readouterr().err.strip()
    assert stderr == "seed-primitives: Invalid primitives catalog: primitives.0.paramsSchema: Field required"
    assert "Traceback" not in stderr
