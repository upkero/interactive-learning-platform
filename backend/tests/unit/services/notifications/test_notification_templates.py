from src.app.services.notifications.notification_service import _render_html, _render_text


def test_russian_completion_email_contains_title_count_and_unsubscribe_link() -> None:
    text = _render_text("ru", "Математика", 3, "https://app.example/materials/1")
    html = _render_html("ru", "Математика", 3, "https://app.example/materials/1")

    assert "Математика" in text
    assert "3" in text
    assert "/profile" in text
    assert "Математика" in html


def test_unknown_locale_uses_english_templates() -> None:
    assert "Your material" in _render_text("de", "Physics", 1, "https://app.example/materials/1")
