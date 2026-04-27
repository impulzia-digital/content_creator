"""Shared image dimension presets for brief UI and agent execution."""

from __future__ import annotations


DEFAULT_ASPECT_RATIO = "4:5"

DEFAULT_IMAGE_DIMENSIONS_BY_ASPECT = {
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}

_IMAGE_DIMENSIONS_BY_PRESET = {
    "1k": DEFAULT_IMAGE_DIMENSIONS_BY_ASPECT,
    "2k": {
        "1:1": (2048, 2048),
        "4:5": (1632, 2048),
        "9:16": (1152, 2048),
        "16:9": (2048, 1152),
    },
    "4k": {
        "1:1": (2880, 2880),
        "4:5": (2560, 3200),
        "9:16": (2160, 3840),
        "16:9": (3840, 2160),
    },
}

IMAGE_RESOLUTION_CHOICES = (
    ("", "— Usar tamaño estándar —"),
    ("1k", "1K Social"),
    ("2k", "2K"),
    ("4k", "4K / Max"),
)

VALID_IMAGE_RESOLUTION_PRESETS = frozenset(_IMAGE_DIMENSIONS_BY_PRESET)


def get_image_dimensions(aspect_ratio: str, preset: str = "1k") -> tuple[int, int]:
    preset_dimensions = _IMAGE_DIMENSIONS_BY_PRESET.get(preset) or _IMAGE_DIMENSIONS_BY_PRESET["1k"]
    return preset_dimensions.get(aspect_ratio, preset_dimensions[DEFAULT_ASPECT_RATIO])


def resolve_image_dimensions(
    *,
    aspect_ratio: str,
    image_overrides: dict | None = None,
) -> tuple[int, int]:
    default_dimensions = get_image_dimensions(aspect_ratio, "1k")
    if not isinstance(image_overrides, dict):
        return default_dimensions

    image_default = image_overrides.get("default")
    if not isinstance(image_default, dict):
        return default_dimensions

    width = image_default.get("width")
    height = image_default.get("height")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        return width, height

    preset = image_default.get("resolution_preset")
    if isinstance(preset, str) and preset in VALID_IMAGE_RESOLUTION_PRESETS:
        return get_image_dimensions(aspect_ratio, preset)

    return default_dimensions