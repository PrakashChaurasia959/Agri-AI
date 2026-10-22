"""Image validation and preprocessing.

The goal of this module is to guarantee that only genuine, decodable raster
images reach the neural network.  Extensions and MIME types are advisory -
the file is decoded with Pillow and the *decoded* properties (format, mode,
dimensions) are what is validated.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Any, BinaryIO

import numpy as np
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

# Pillow refuses to decode images larger than this by default (decompression
# bomb protection).  We keep the protection but raise the ceiling slightly
# above the maximum accepted pixel dimension.
Image.MAX_IMAGE_PIXELS = 80_000_000

SUPPORTED_FORMATS: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

# Formats Pillow can decode that we deliberately do not accept.
REJECTED_FORMATS: dict[str, str] = {
    "SVG": "image/svg+xml",
    "PDF": "application/pdf",
    "TIFF": "image/tiff",
    "GIF": "image/gif",
    "ICO": "image/x-icon",
    "BMP": "image/bmp",
}


class ImageValidationError(ValueError):
    """Raised when an uploaded file is not an acceptable image."""

    def __init__(self, message: str, code: str = "invalid_image") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class ImageInfo:
    """Metadata about a validated image."""

    width: int
    height: int
    format: str
    mode: str
    mime_type: str
    file_size: int
    aspect_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "mode": self.mode,
            "mime_type": self.mime_type,
            "file_size": self.file_size,
            "aspect_ratio": round(self.aspect_ratio, 4),
        }


@dataclass(frozen=True)
class PreprocessConfig:
    """Preprocessing parameters (mirrors :class:`ml.config.InferenceConfig`)."""

    image_size: int = 224
    rescale_factor: float = 1.0 / 255.0
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    std: tuple[float, float, float] = (0.229, 0.224, 0.225)
    interpolation: str = "bilinear"


def validate_image_bytes(
    data: bytes,
    *,
    max_bytes: int = 10 * 1024 * 1024,
    min_dimension: int = 32,
    max_dimension: int = 8000,
    allowed_mime_types: list[str] | None = None,
) -> ImageInfo:
    """Validate raw image bytes.

    Raises :class:`ImageValidationError` when the payload is empty, too large,
    not a real image, in an unsupported format, or has implausible dimensions.
    """
    if not data:
        raise ImageValidationError("The uploaded file is empty.", "empty_file")

    if len(data) > max_bytes:
        size_mb = len(data) / (1024 * 1024)
        raise ImageValidationError(
            f"The image is too large ({size_mb:.1f} MB). The maximum allowed size is "
            f"{max_bytes / (1024 * 1024):.0f} MB.",
            "file_too_large",
        )

    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()  # structural check - raises on malformed files
    except UnidentifiedImageError:
        raise ImageValidationError(
            "The uploaded file is not a recognised image. Please upload a JPEG, PNG or WebP file.",
            "not_an_image",
        )
    except Image.DecompressionBombError:
        raise ImageValidationError(
            "The image dimensions are too large to process safely.", "image_too_large"
        )
    except OSError:
        raise ImageValidationError(
            "The uploaded file appears to be corrupted and could not be read.",
            "corrupt_image",
        )

    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
            mode = image.mode
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageValidationError(
            "The uploaded file appears to be corrupted and could not be read.",
            "corrupt_image",
        ) from exc

    if image_format in REJECTED_FORMATS:
        raise ImageValidationError(
            f"{image_format} files are not supported. Please upload a JPEG, PNG or WebP image.",
            "unsupported_format",
        )

    if image_format not in SUPPORTED_FORMATS:
        raise ImageValidationError(
            f"Unsupported image format '{image_format or 'unknown'}'. "
            "Please upload a JPEG, PNG or WebP image.",
            "unsupported_format",
        )

    mime_type = SUPPORTED_FORMATS[image_format]
    if allowed_mime_types and mime_type not in allowed_mime_types:
        raise ImageValidationError(
            f"Image type '{mime_type}' is not accepted. "
            f"Allowed types: {', '.join(allowed_mime_types)}.",
            "unsupported_format",
        )

    if width < min_dimension or height < min_dimension:
        raise ImageValidationError(
            f"The image is too small ({width}x{height} pixels). "
            f"Images must be at least {min_dimension}x{min_dimension} pixels.",
            "image_too_small",
        )

    if width > max_dimension or height > max_dimension:
        raise ImageValidationError(
            f"The image is too large ({width}x{height} pixels). "
            f"Images must not exceed {max_dimension}x{max_dimension} pixels.",
            "image_too_large",
        )

    return ImageInfo(
        width=width,
        height=height,
        format=image_format,
        mode=mode,
        mime_type=mime_type,
        file_size=len(data),
        aspect_ratio=width / height if height else 0.0,
    )


def preprocess_image(
    data: bytes,
    config: PreprocessConfig | None = None,
) -> np.ndarray:
    """Decode and preprocess an image into a batch-ready float array.

    The output shape is ``(1, H, W, 3)`` with values normalised the same way
    the training pipeline normalised them.
    """
    config = config or PreprocessConfig()

    try:
        with Image.open(io.BytesIO(data)) as image:
            image = image.convert("RGB")
            resample = {
                "bilinear": Image.Resampling.BILINEAR,
                "bicubic": Image.Resampling.BICUBIC,
                "lanczos": Image.Resampling.LANCZOS,
                "nearest": Image.Resampling.NEAREST,
            }.get(config.interpolation, Image.Resampling.BILINEAR)
            image = image.resize(
                (config.image_size, config.image_size), resample=resample
            )
            array = np.asarray(image, dtype=np.float32)
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageValidationError(
            "The uploaded file appears to be corrupted and could not be read.",
            "corrupt_image",
        ) from exc

    if array.ndim != 3 or array.shape[2] != 3:
        raise ImageValidationError(
            "The image could not be converted to RGB colour space.",
            "invalid_image",
        )

    array = array / 255.0
    mean = np.asarray(config.mean, dtype=np.float32)
    std = np.asarray(config.std, dtype=np.float32)
    array = (array - mean) / std
    return np.expand_dims(array.astype(np.float32), axis=0)


def read_upload(file: BinaryIO, max_bytes: int) -> bytes:
    """Read an upload in bounded chunks so a huge body cannot exhaust memory."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ImageValidationError(
                f"The image is larger than the {max_bytes / (1024 * 1024):.0f} MB limit.",
                "file_too_large",
            )
        chunks.append(chunk)
    return b"".join(chunks)
