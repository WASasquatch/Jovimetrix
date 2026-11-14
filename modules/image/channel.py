"""Channel operations: solid fills, merging planes and swapping channels between frames."""

from __future__ import annotations

import torch

from ..params import IMAGE_SIZE_MIN

from ..enums import EnumImageType, EnumPixelSwizzle, EnumScaleMode

from . import PixelType, ImageType

from .convert import image_convert

from .compose import image_scalefit, image_matte

from .pixel import pixel_eval

# ==============================================================================
# === CHANNEL ===
# ==============================================================================

def channel_solid(width: int = IMAGE_SIZE_MIN, height: int = IMAGE_SIZE_MIN,
                  color: PixelType = (0, 0, 0, 255), chan: EnumImageType = EnumImageType.RGB) -> ImageType:
    """Build a frame of one solid colour.

    Args:
        width: Width in pixels.
        height: Height in pixels.
        color: Level or RGB(A) colour, 0 to 255.
        chan: Channel layout of the result.

    Returns:
        The frame.
    """
    if chan == EnumImageType.GRAYSCALE:
        level = float(pixel_eval(color, EnumImageType.GRAYSCALE)) / 255.0
        return torch.full((height, width, 1), level)

    if not isinstance(color, (list, set, tuple)):
        color = [color]
    color = tuple(color) + (0,) * (3 - len(color))
    if chan in (EnumImageType.BGR, EnumImageType.RGB):
        values = color[2::-1] if chan == EnumImageType.BGR else color[:3]
    else:
        if len(color) < 4:
            color += (255,)
        values = tuple(color[2::-1]) + (color[3],) if chan == EnumImageType.BGRA else color[:4]
    return torch.tensor([float(v) / 255.0 for v in values]).repeat(height, width, 1)


def channel_merge(channels: list[ImageType]) -> ImageType:
    """Stack single-channel planes into one frame, centring planes of differing size.

    Args:
        channels: One plane per output channel; ``None`` leaves that channel black.

    Returns:
        The merged frame.
    """
    present = [ch for ch in channels if ch is not None]
    max_height = max(ch.shape[0] for ch in present)
    max_width = max(ch.shape[1] for ch in present)
    output = torch.zeros((max_height, max_width, len(channels)), dtype=present[0].dtype)
    for i, channel in enumerate(channels):
        if channel is None:
            continue
        if channel.ndim == 3:
            channel = channel[..., 0]
        h, w = channel.shape[:2]
        top = (max_height - h) // 2
        left = (max_width - w) // 2
        output[top:top + h, left:left + w, i] = channel
    return output


def channel_swap(imgA: ImageType, imgB: ImageType, swap_in: tuple[EnumPixelSwizzle, ...],
                 matte: tuple[int, ...] = (0, 0, 0, 255)) -> ImageType:
    """Build an RGBA frame whose channels each come from frame A, frame B or a constant.

    Args:
        imgA: Frame A.
        imgB: Frame B, fitted to A's size.
        swap_in: Source of the red, green, blue and alpha channels, in that order.
        matte: RGBA constant used by a ``CONSTANT`` source, 0 to 255.

    Returns:
        The RGBA frame.
    """
    imgA = image_convert(imgA, 4)
    h, w = imgA.shape[:2]
    imgB = image_convert(imgB, 4)
    imgB = image_matte(imgB, (0, 0, 0, 0), w, h)
    imgB = image_scalefit(imgB, w, h, EnumScaleMode.CROP)
    out = channel_solid(w, h, tuple(matte), EnumImageType.RGBA).to(imgA.dtype)
    for target, swap in enumerate(swap_in):
        if swap != EnumPixelSwizzle.CONSTANT:
            source = (imgA, imgB)[swap.value % 10]
            out[:, :, target] = source[:, :, swap.value // 10]
    return out
