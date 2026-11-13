"""Image helpers on numpy arrays shaped ``(H, W, C)``, ``uint8`` in ``[0, 255]``.

Channel order is RGB or RGBA unless a function says otherwise. Importing the package needs OpenCV.
"""

from __future__ import annotations

import math
from typing import Any, TypeAlias, Union

import numpy as np

from .. import deps
from ..enums import EnumImageType

deps.require("cv2")

RGB_Int: TypeAlias = tuple[int, int, int]
RGBA_Int: TypeAlias = tuple[int, int, int, int]
RGB_Float: TypeAlias = tuple[float, float, float]
RGBA_Float: TypeAlias = tuple[float, float, float, float]

Coord2D_Int: TypeAlias = tuple[int, int]
Coord3D_Int: TypeAlias = tuple[int, int, int]
Coord2D_Float: TypeAlias = tuple[float, float]
Coord3D_Float: TypeAlias = tuple[float, float, float]

ImageType: TypeAlias = np.ndarray[Any, np.dtype[Any]]
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
