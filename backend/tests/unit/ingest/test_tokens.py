import pytest
from pydantic import ValidationError

from src.app.core.settings.ingest import IngestSettings
from src.app.ingest.tokens import TokenCounter


@pytest.mark.unit
def test_calibrated_count_rounds_up_and_empty_is_zero() -> None:
    counter = TokenCounter(calibration=1.15)
    assert counter.count("") == 0
    assert counter.count_raw("a") == 1
    assert counter.count("a") == 2
    assert counter.count("Пример текста") == int(counter.count_raw("Пример текста") * 1.15) + 1


@pytest.mark.unit
def test_settings_use_shared_environment_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKENS_CALIBRATION", "1.31")
    monkeypatch.setenv("SPLIT_TARGET_TOKENS", "7000")
    monkeypatch.setenv("SPLIT_MAX_TOKENS", "7777")
    settings = IngestSettings()
    assert settings.tokens_calibration == 1.31
    assert settings.split_target_tokens == 7000
    assert settings.segment_max_tokens == 7777


@pytest.mark.unit
def test_split_target_must_not_exceed_maximum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPLIT_TARGET_TOKENS", "30000")
    monkeypatch.setenv("SPLIT_MAX_TOKENS", "22000")
    with pytest.raises(ValidationError, match="SPLIT_TARGET_TOKENS"):
        IngestSettings()


@pytest.mark.unit
def test_prefixed_split_variables_are_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPLIT_TARGET_TOKENS", raising=False)
    monkeypatch.delenv("SPLIT_MAX_TOKENS", raising=False)
    monkeypatch.setenv("INGEST_SPLIT_TARGET_TOKENS", "50")
    monkeypatch.setenv("INGEST_SPLIT_MAX_TOKENS", "25")
    settings = IngestSettings(_env_file=None)
    assert (settings.split_target_tokens, settings.split_max_tokens) == (15_000, 22_000)
