"""OpenCV's 22 colour maps and lookups through 256 entry tables.

``data/opencv_colormaps.png`` holds one 256 pixel row per map, in ``EnumColorMap`` order,
sampled from OpenCV 4.13's ``applyColorMap`` (Apache 2.0; see NOTICE).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import torch

TABLE = Path(__file__).resolve().parent / "data" / "opencv_colormaps.png"


@lru_cache(maxsize=1)
def _table() -> torch.Tensor:
    import numpy as np
    from PIL import Image

    with Image.open(TABLE) as img:
        rows = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(rows)


def colormap(index: int) -> torch.Tensor:
    """Return one of OpenCV's colour maps.

    Args:
        index: ``EnumColorMap`` value, 0 to 21.

    Returns:
        ``(256, 3)`` RGB table, 0 to 1.
    """
    table = _table()
    return table[int(max(0, min(table.shape[0] - 1, index)))]


def apply_lut(gray: torch.Tensor, lut: torch.Tensor) -> torch.Tensor:
    """Look every grey level up in a 256 entry table.

    Args:
        gray: ``(H, W)`` or ``(H, W, 1)`` levels, 0 to 1.
        lut: ``(256, C)`` table.

    Returns:
        ``(H, W, C)`` frame.
    """
    if gray.ndim == 3:
        gray = gray[..., 0]
    index = (gray.clamp(0, 1) * 255).round().long()
    return lut.to(device=gray.device, dtype=gray.dtype)[index]
