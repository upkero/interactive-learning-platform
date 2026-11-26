import pytest

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
    monkeypatch.setenv("SPLIT_MAX_TOKENS", "7777")
    settings = IngestSettings()
    assert settings.tokens_calibration == 1.31
    assert settings.segment_max_tokens == 7777
