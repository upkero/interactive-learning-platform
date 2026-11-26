"""Reader profile of the generation wizard (screen Э4)."""

import pytest

from src.app.contracts.solver.main_pass import ReaderProfile

pytestmark = pytest.mark.unit


def test_reader_profile_is_read_from_the_stored_part_mapping() -> None:
    profile = ReaderProfile.from_mapping({"level": "advanced", "goal": "exam", "depth": "deep"})

    assert profile == ReaderProfile(level="advanced", goal="exam", depth="deep")


@pytest.mark.parametrize(
    "raw",
    (
        {},
        {"level": "expert", "goal": "exam", "depth": "deep"},
        {"level": "novice", "goal": "fun", "depth": "deep"},
        {"level": "novice", "goal": "exam", "depth": "full"},
    ),
)
def test_reader_profile_rejects_unknown_values(raw: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="Unknown reader profile"):
        ReaderProfile.from_mapping(raw)
