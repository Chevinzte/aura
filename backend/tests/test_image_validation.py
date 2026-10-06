from hashlib import sha256
from io import BytesIO

import pytest
from PIL import Image

from aura_backend.media.images import (
    ImageTooLarge,
    ImageTooSmall,
    ImageValidator,
    UnsupportedImageType,
)


def make_image(*, size: tuple[int, int] = (300, 300), image_format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", size, "pink").save(output, format=image_format)
    return output.getvalue()


def test_valid_image_is_measured_hashed_and_normalized() -> None:
    data = make_image()
    validator = ImageValidator(max_bytes=1_000_000, min_dimension=256)

    image = validator.validate(data, "image/png")

    assert image.width_px == 300
    assert image.height_px == 300
    assert image.extension == "png"
    assert image.content_sha256 == sha256(data).hexdigest()
    assert image.analysis_data


def test_rejects_mime_type_that_does_not_match_contents() -> None:
    validator = ImageValidator(max_bytes=1_000_000, min_dimension=256)

    with pytest.raises(UnsupportedImageType):
        validator.validate(make_image(), "image/jpeg")


def test_rejects_large_or_small_images() -> None:
    with pytest.raises(ImageTooLarge):
        ImageValidator(max_bytes=10, min_dimension=1).validate(make_image(), "image/png")

    with pytest.raises(ImageTooSmall):
        ImageValidator(max_bytes=1_000_000, min_dimension=256).validate(
            make_image(size=(255, 300)), "image/png"
        )
