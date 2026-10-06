from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


class ImageValidationError(ValueError):
    """Base error for an image that cannot enter AURA's AI pipeline."""

    code = "INVALID_IMAGE"


class UnsupportedImageType(ImageValidationError):
    code = "UNSUPPORTED_IMAGE_TYPE"


class ImageTooLarge(ImageValidationError):
    code = "IMAGE_TOO_LARGE"


class ImageTooSmall(ImageValidationError):
    code = "IMAGE_TOO_SMALL"


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    original_data: bytes
    analysis_data: bytes
    mime_type: str
    extension: str
    width_px: int
    height_px: int
    size_bytes: int
    content_sha256: str


class ImageValidator:
    """Validate uploads and normalize orientation before vision analysis."""

    _format_details = {
        "JPEG": ("image/jpeg", "jpg"),
        "PNG": ("image/png", "png"),
        "WEBP": ("image/webp", "webp"),
    }

    def __init__(
        self,
        *,
        max_bytes: int,
        min_dimension: int,
        max_pixels: int = 40_000_000,
    ) -> None:
        self._max_bytes = max_bytes
        self._min_dimension = min_dimension
        self._max_pixels = max_pixels

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def validate(self, data: bytes, declared_mime_type: str | None) -> ValidatedImage:
        if not data:
            raise ImageValidationError("Image file is empty")
        if len(data) > self._max_bytes:
            raise ImageTooLarge("Image exceeds the configured upload limit")

        normalized_mime = (declared_mime_type or "").lower().split(";", 1)[0].strip()
        if normalized_mime not in {details[0] for details in self._format_details.values()}:
            raise UnsupportedImageType("Only JPEG, PNG, and WebP images are accepted")

        try:
            with Image.open(BytesIO(data)) as opened_image:
                opened_image.verify()
            with Image.open(BytesIO(data)) as opened_image:
                detected_format = opened_image.format
                if detected_format not in self._format_details:
                    raise UnsupportedImageType("Only JPEG, PNG, and WebP images are accepted")
                detected_mime, extension = self._format_details[detected_format]
                if normalized_mime != detected_mime:
                    raise UnsupportedImageType("Declared image type does not match file contents")
                if opened_image.width * opened_image.height > self._max_pixels:
                    raise ImageTooLarge("Image has too many pixels to process safely")

                normalized_image = ImageOps.exif_transpose(opened_image)
                normalized_image.load()
                width_px, height_px = normalized_image.size
                if min(width_px, height_px) < self._min_dimension:
                    raise ImageTooSmall(
                        f"Image dimensions must be at least {self._min_dimension}px per side"
                    )

                output = BytesIO()
                save_options: dict[str, object] = {}
                if detected_format == "JPEG":
                    normalized_image = normalized_image.convert("RGB")
                    save_options = {"quality": 92, "optimize": True}
                normalized_image.save(output, format=detected_format, **save_options)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise ImageValidationError("Image file could not be decoded safely") from error

        return ValidatedImage(
            original_data=data,
            analysis_data=output.getvalue(),
            mime_type=detected_mime,
            extension=extension,
            width_px=width_px,
            height_px=height_px,
            size_bytes=len(data),
            content_sha256=sha256(data).hexdigest(),
        )
