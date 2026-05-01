"""Book cover border detection and edge color sampling helpers."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image

from app.core.config import settings


@dataclass(slots=True)
class ProcessedCover:
    image_bytes: bytes
    mime_type: str
    edge_colors: dict[str, str]
    crop_bounds: dict[str, int]


def detect_border_region(img: Image.Image) -> tuple[int, int, int, int]:
    """Return crop bounds for the non-border region."""
    rgba = img.convert("RGBA")
    arr = np.asarray(rgba)
    height, width = arr.shape[:2]
    if height <= 2 or width <= 2:
        return 0, 0, width, height

    sample = max(1, min(settings.COVER_EDGE_SAMPLE_SIZE, max(1, min(width, height) // 8)))
    threshold = max(0.0, float(settings.COVER_BORDER_VARIANCE_THRESHOLD))

    top = _scan_from_top(arr, sample, threshold)
    bottom = _scan_from_bottom(arr, sample, threshold)
    left = _scan_from_left(arr, sample, threshold)
    right = _scan_from_right(arr, sample, threshold)

    x = max(0, left)
    y = max(0, top)
    crop_width = max(1, width - left - right)
    crop_height = max(1, height - top - bottom)

    pad_x = int(round(crop_width * float(settings.COVER_FINAL_PADDING_PCT)))
    pad_y = int(round(crop_height * float(settings.COVER_FINAL_PADDING_PCT)))

    x = max(0, x - pad_x)
    y = max(0, y - pad_y)
    right_edge = min(width, x + crop_width + pad_x * 2)
    bottom_edge = min(height, y + crop_height + pad_y * 2)

    if right_edge <= x or bottom_edge <= y:
        return 0, 0, width, height
    return x, y, right_edge - x, bottom_edge - y


def sample_edge_colors(img: Image.Image, crop_bounds: tuple[int, int, int, int]) -> dict[str, str]:
    """Sample representative colors from the cropped cover edges."""
    x, y, width, height = crop_bounds
    cropped = img.convert("RGBA").crop((x, y, x + width, y + height))
    arr = np.asarray(cropped)
    if arr.size == 0:
        fallback = _hex_from_rgb((128, 128, 128))
        return {edge: fallback for edge in ("top", "bottom", "left", "right", "dominant")}

    strip = max(1, min(settings.COVER_EDGE_SAMPLE_SIZE, max(1, int(round(min(width, height) * 0.05)))))
    samples = {
        "top": _median_hex(arr[:strip, :, :]),
        "bottom": _median_hex(arr[max(0, height - strip):, :, :]),
        "left": _median_hex(arr[:, :strip, :]),
        "right": _median_hex(arr[:, max(0, width - strip):, :]),
    }
    dominant = _median_hex(_stack_visible_pixels(arr))
    samples["dominant"] = dominant
    return samples


def process_cover(image_bytes: bytes) -> ProcessedCover:
    """Load, crop, and sample a cover image."""
    with Image.open(BytesIO(image_bytes)) as source:
        source.load()
        bounds = detect_border_region(source)
        cropped = source.convert("RGBA").crop((bounds[0], bounds[1], bounds[0] + bounds[2], bounds[1] + bounds[3]))
        output = BytesIO()
        cropped.save(output, format="PNG", optimize=True)
        edge_colors = sample_edge_colors(source, bounds)
        return ProcessedCover(
            image_bytes=output.getvalue(),
            mime_type="image/png",
            edge_colors=edge_colors,
            crop_bounds={"x": bounds[0], "y": bounds[1], "width": bounds[2], "height": bounds[3]},
        )


def _scan_from_top(arr: np.ndarray, sample: int, threshold: float) -> int:
    height = arr.shape[0]
    offset = 0
    while offset < height - 1:
        strip = arr[offset:min(height, offset + sample), :, :]
        if _normalized_variance(strip) >= threshold:
            break
        offset += sample
    return min(offset, height - 1)


def _scan_from_bottom(arr: np.ndarray, sample: int, threshold: float) -> int:
    height = arr.shape[0]
    offset = 0
    while offset < height - 1:
        strip = arr[max(0, height - offset - sample):height - offset, :, :]
        if _normalized_variance(strip) >= threshold:
            break
        offset += sample
    return min(offset, height - 1)


def _scan_from_left(arr: np.ndarray, sample: int, threshold: float) -> int:
    width = arr.shape[1]
    offset = 0
    while offset < width - 1:
        strip = arr[:, offset:min(width, offset + sample), :]
        if _normalized_variance(strip) >= threshold:
            break
        offset += sample
    return min(offset, width - 1)


def _scan_from_right(arr: np.ndarray, sample: int, threshold: float) -> int:
    width = arr.shape[1]
    offset = 0
    while offset < width - 1:
        strip = arr[:, max(0, width - offset - sample):width - offset, :]
        if _normalized_variance(strip) >= threshold:
            break
        offset += sample
    return min(offset, width - 1)


def _normalized_variance(strip: np.ndarray) -> float:
    if strip.size == 0:
        return 0.0
    rgb = strip[:, :, :3].astype(np.float32) / 255.0
    if rgb.size == 0:
        return 0.0
    return float(np.var(rgb))


def _stack_visible_pixels(arr: np.ndarray) -> np.ndarray:
    rgba = arr.reshape(-1, arr.shape[-1])
    visible = rgba[rgba[:, 3] > 0]
    if visible.size == 0:
        visible = rgba
    return visible[:, :3]


def _median_hex(pixels: np.ndarray) -> str:
    if pixels.size == 0:
        return _hex_from_rgb((128, 128, 128))
    rgb = np.median(pixels[..., :3].reshape(-1, 3), axis=0)
    return _hex_from_rgb(tuple(int(round(component)) for component in rgb))


def _hex_from_rgb(rgb: tuple[int, ...]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, component)) for component in rgb[:3]))
