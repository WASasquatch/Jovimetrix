"""Frame list helpers: sizing a set of frames and stacking node results."""

from __future__ import annotations

import sys

import torch

from ..params import RGBAMaskType

from ..enums import EnumImageBySize

from . import ImageType

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def image_by_size(image_list: list[ImageType],
                  enumSize: EnumImageBySize = EnumImageBySize.LARGEST) -> tuple[ImageType, int, int]:
    """Pick a frame by size and report the width and height that rule settles on.

    Args:
        image_list: Frames.
        enumSize: LARGEST and SMALLEST also give the largest or smallest width and height
            across all frames; the others give the chosen extreme of one side.

    Returns:
        ``(frame, width, height)``.
    """
    img = None
    mega, width, height = 0, 0, 0
    if enumSize in (EnumImageBySize.SMALLEST, EnumImageBySize.WIDTH_MIN, EnumImageBySize.HEIGHT_MIN):
        mega, width, height = sys.maxsize, sys.maxsize, sys.maxsize

    for i in image_list:
        h, w = i.shape[:2]
        match enumSize:
            case EnumImageBySize.LARGEST:
                if (new_mega := w * h) > mega:
                    mega = new_mega
                    img = i
                width = max(width, w)
                height = max(height, h)
            case EnumImageBySize.SMALLEST:
                if (new_mega := w * h) < mega:
                    mega = new_mega
                    img = i
                width = min(width, w)
                height = min(height, h)
            case EnumImageBySize.WIDTH_MIN:
                if w < width:
                    width = w
                    img = i
            case EnumImageBySize.WIDTH_MAX:
                if w > width:
                    width = w
                    img = i
            case EnumImageBySize.HEIGHT_MIN:
                if h < height:
                    height = h
                    img = i
            case EnumImageBySize.HEIGHT_MAX:
                if h > height:
                    height = h
                    img = i
    return img, width, height


def image_minmax(image: list[ImageType]) -> tuple[int, int, int, int]:
    """Smallest and largest width and height across frames: ``(w_min, h_min, w_max, h_max)``."""
    h_min = w_min = 100000000000
    h_max = w_max = 1
    for img in image:
        if img is None:
            continue
        h, w = img.shape[:2]
        h_max = max(h, h_max)
        w_max = max(w, w_max)
        h_min = min(h, h_min)
        w_min = min(w, w_min)
    return w_min, h_min, w_max, h_max


def image_stack(images: list[ImageType]) -> RGBAMaskType:
    """Stack per-frame ``(RGBA, RGB, MASK)`` results into three batches."""
    return [torch.stack(i) for i in zip(*images)]
