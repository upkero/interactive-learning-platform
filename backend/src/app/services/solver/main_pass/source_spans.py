"""Find model-quoted source fragments without trusting model-computed offsets."""

import re
from collections.abc import Sequence

from src.app.contracts.solver.main_pass import DirectiveSpan, MainPassDirective
from src.app.services.solver.main_pass.directives import Directive


def locate_spans(
    directives: Sequence[Directive] | Sequence[MainPassDirective], source_markdown: str
) -> tuple[DirectiveSpan, ...]:
    """Return offsets into the original text, treating whitespace runs as equivalent."""
    spans: list[DirectiveSpan] = []
    for directive in directives:
        words = directive.source_span.split()
        pattern = r"\s+".join(re.escape(word) for word in words)
        match = re.search(pattern, source_markdown) if pattern else None
        spans.append(
            DirectiveSpan(
                ref=directive.ref,
                kind=directive.kind,
                start=match.start() if match else None,
                end=match.end() if match else None,
            )
        )
    return tuple(spans)
