"""Localized human-readable progress messages."""

from src.app.contracts.progress import ProgressEventType

_MESSAGES: dict[str, dict[str, str]] = {
    "ru": {
        "main_pass": "Разбираю часть {part}",
        "resolving": "Собираю виджеты в части {part}",
        "assembling": "Готовлю часть {part}",
        "published": "Часть {part} готова",
        "document_done": "Материал готов",
        "failed": "Обработка завершилась с ошибкой",  # noqa: RUF001
    },
    "en": {
        "main_pass": "Analyzing part {part}",
        "resolving": "Collecting widgets in part {part}",
        "assembling": "Preparing part {part}",
        "published": "Part {part} is ready",
        "document_done": "Your material is ready",
        "failed": "Processing finished with an error",
    },
}


def render_message(locale: str, event_type: ProgressEventType, stage: str | None, params: dict[str, object]) -> str:
    language = locale if locale in _MESSAGES else "en"
    key = stage or event_type.value
    template = _MESSAGES[language].get(key, key.replace("_", " ").capitalize())
    return template.format(**params) if params else template
