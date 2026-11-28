"""Fallback outcome when no resolution succeeds (story 2.4.7)."""


from src.app.contracts.solver.main_pass import MainPassDirective
from src.app.contracts.solver.resolve import ResolveOutcome


def fallback_outcome(request: MainPassDirective) -> ResolveOutcome:
    """Create a fallback outcome: image if available, otherwise text."""
    image_ids = request.image_ids or {}
    image_uuid = image_ids.get(request.directive.image_id or "") if request.directive.image_id else None

    if image_uuid:
        params: dict[str, object] = {"fallback": "image", "image_id": str(image_uuid)}
    else:
        params = {"fallback": "text"}

    return ResolveOutcome(
        directive_ref=request.directive_ref,
        decision="fallback",
        status="fallback",
        widget_id=None,
        params=params,
    )


__all__ = ["fallback_outcome"]