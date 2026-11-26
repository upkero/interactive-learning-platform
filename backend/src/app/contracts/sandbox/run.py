"""Typed internal sandbox contract; screenshots are the PNG bytes as base64."""

from dataclasses import dataclass
from typing import Literal

from src.app.contracts.llm.image_part import ImagePart

SandboxMode = Literal["watch", "steps", "predict"]


@dataclass(frozen=True, slots=True)
class SandboxRunRequest:
    source_tsx: str
    param_sets: tuple[dict[str, object], ...]
    mode: SandboxMode = "watch"
    labels: dict[str, str] | None = None
    locale: str = "en"
    viewport_width: int = 800
    viewport_height: int = 500


@dataclass(frozen=True, slots=True)
class SandboxRunResult:
    ok: bool
    compiled_js: str | None
    console_errors: tuple[str, ...]
    screenshots_png_base64: tuple[str, ...]
    timings: dict[str, object]

    @property
    def images(self) -> tuple[ImagePart, ...]:
        """Pass screenshots to the judge without decoding and re-encoding them."""
        return tuple(ImagePart(media_type="image/png", data_base64=shot) for shot in self.screenshots_png_base64)
