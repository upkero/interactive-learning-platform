"""Image inside a multimodal message (base64)."""

from dataclasses import dataclass
from typing import Literal

ImageMediaType = Literal["image/png", "image/jpeg"]


@dataclass(frozen=True, slots=True)
class ImagePart:
    media_type: ImageMediaType
    data_base64: str
