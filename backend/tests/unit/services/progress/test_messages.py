from src.app.contracts.progress import ProgressEventType
from src.app.services.progress.messages import render_message


def test_render_message_uses_locale_and_stage() -> None:
    assert render_message("ru", ProgressEventType.PART_STATUS, "published", {"part": 2}) == "Часть 2 готова"
    assert render_message("en", ProgressEventType.PART_STATUS, "main_pass", {"part": 3}) == "Analyzing part 3"


def test_render_message_falls_back_to_english() -> None:
    assert render_message("de", ProgressEventType.DOCUMENT_DONE, None, {}) == "Your material is ready"
