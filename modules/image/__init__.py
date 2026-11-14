"""Image helpers on frames: one picture as a float tensor shaped ``(H, W, C)``, 0 to 1.

C is 1, 3 or 4, in RGB or RGBA order. Everything here runs on torch, numpy, Pillow and scipy,
which ComfyUI itself installs.
"""

from __future__ import annotations

import math
from typing import TypeAlias, Union

import torch

from ..enums import EnumImageType

RGB_Int: TypeAlias = tuple[int, int, int]
RGBA_Int: TypeAlias = tuple[int, int, int, int]
RGB_Float: TypeAlias = tuple[float, float, float]
RGBA_Float: TypeAlias = tuple[float, float, float, float]

Coord2D_Int: TypeAlias = tuple[int, int]
Coord3D_Int: TypeAlias = tuple[int, int, int]
Coord2D_Float: TypeAlias = tuple[float, float]
Coord3D_Float: TypeAlias = tuple[float, float, float]

ImageType: TypeAlias = torch.Tensor
PixelType: TypeAlias = Union[int, float, RGB_Int, RGBA_Int, RGB_Float, RGBA_Float]

HALFPI: float = math.pi / 2
TAU: float = math.pi * 2


def image_formats() -> list[str]:
    """Return every file extension Pillow can open, such as ``".png"``.

    Returns:
        Lower-case extensions with their dot.
    """
    from PIL import Image

    return [ext for ext, fmt in Image.registered_extensions().items() if fmt in Image.OPEN]


__all__ = [
    "EnumImageType", "ImageType", "PixelType", "RGB_Int", "RGBA_Int", "RGB_Float", "RGBA_Float",
    "Coord2D_Int", "Coord3D_Int", "Coord2D_Float", "Coord3D_Float", "HALFPI", "TAU",
    "image_formats",
]
