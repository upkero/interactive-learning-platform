"""Localized human-readable progress messages."""

from src.app.contracts.progress import ProgressEventType

_MESSAGES: dict[str, dict[str, str]] = {
    "ru": {
        "main_pass": "Разбираю часть {part}",
        "resolving": "Собираю виджеты в части {part}",
        "assembling": "Готовлю часть {part}",
        "published": "Часть {part} готова",
        "part_ready": "Часть готова",
        "queued": "Часть {part} ожидает обработки",
        "document_done": "Материал готов",
        "failed": "Обработка завершилась с ошибкой",  # noqa: RUF001
        "document_failed": "Не получилось подготовить материал",  # noqa: RUF001
        "error": "Произошла ошибка",
        "unknown": "Обновление состояния материала",
    },
    "en": {
        "main_pass": "Analyzing part {part}",
        "resolving": "Collecting widgets in part {part}",
        "assembling": "Preparing part {part}",
        "published": "Part {part} is ready",
        "part_ready": "Part ready",
        "queued": "Part {part} is queued",
        "document_done": "Your material is ready",
        "failed": "Processing finished with an error",
        "document_failed": "Could not prepare your material",
        "error": "An error occurred",
        "unknown": "Material status update",
    },
}


def render_message(locale: str, event_type: ProgressEventType, stage: str | None, params: dict[str, object]) -> str:
    language = locale if locale in _MESSAGES else "en"
    key = (
        ("document_failed" if params.get("outcome") == "failed" or stage == "failed" else "document_done")
        if event_type is ProgressEventType.DOCUMENT_DONE
        else stage or event_type.value
    )
    template = _MESSAGES[language].get(key, _MESSAGES[language]["unknown"])
    try:
        return template.format(**params)
    except (KeyError, ValueError, IndexError):
        return _MESSAGES[language]["unknown"]
