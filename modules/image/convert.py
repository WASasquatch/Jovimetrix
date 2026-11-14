"""Conversions between ComfyUI tensors, frames and Pillow images, and channel reshaping.

A frame is one picture as a float tensor shaped ``(H, W, C)``, 0 to 1, with C of 1, 3 or 4.
Colours passed in as numbers (mattes, fills) stay on the 0 to 255 scale nodes use.
"""

from __future__ import annotations

import numpy as np
import torch
from PIL import Image

from . import RGBA_Int, ImageType

from .space import gray, linear_to_srgb, srgb_to_linear

__all__ = [
    "image_convert", "image_grayscale", "image_mask", "image_mask_add", "image_mask_binary",
    "frame_to_pil", "frame_tensor", "frame_outputs", "pil_to_frame", "to_frame", "tensor_to_pil",
    "srgb_to_linear", "linear_to_srgb",
]

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def _levels(color, count: int, device, dtype) -> torch.Tensor:
    """A 0 to 255 colour as ``count`` levels on 0 to 1."""
    values = [float(c) / 255.0 for c in (tuple(color) if isinstance(color, (list, tuple)) else (color,))]
    values = (values + [values[-1]] * count)[:count] if len(values) < count else values[:count]
    return torch.tensor(values, dtype=dtype, device=device)


def image_convert(image: ImageType, channels: int, width: int = 0, height: int = 0,
                  matte: RGBA_Int = (0, 0, 0, 255)) -> ImageType:
    """Give a frame a channel count and, optionally, a canvas size.

    Args:
        image: Frame, ``(H, W)`` or ``(H, W, C)``.
        channels: 1, 3 or 4.
        width: Canvas width; 0 keeps the width.
        height: Canvas height; 0 keeps the height.
        matte: RGBA, 0 to 255, of the canvas around a frame smaller than it, and the alpha
            added to a frame that has none.

    Returns:
        The frame. On a larger canvas the picture is centred and the surround is transparent;
        a picture larger than the canvas is cut to it around the centre.
    """
    if image.ndim == 2:
        image = image.unsqueeze(-1)
    cc = image.shape[2]
    if cc == 1 and channels in (3, 4):
        image = image.expand(-1, -1, 3)
        cc = 3
    if cc == 3 and channels == 4:
        alpha = torch.full_like(image[..., :1], float(tuple(matte)[3]) / 255.0)
        image = torch.cat([image, alpha], dim=2)
    elif cc == 4 and channels == 3:
        image = image[..., :3]
    elif cc == 4 and channels == 1:
        image = image[..., :3].mean(dim=2, keepdim=True) * image[..., 3:4]
    elif cc != 1 and channels == 1:
        image = image_grayscale(image)

    h, w = image.shape[:2]
    width = width if width > 0 else w
    height = height if height > 0 else h
    if (width, height) == (w, h):
        return image.contiguous()

    c = image.shape[2]
    base = _levels(matte, 4, image.device, image.dtype)
    base = torch.cat([base[:3], base.new_zeros(1)]) if c == 4 else base[:c]
    canvas = base.repeat(height, width, 1)
    ox, oy = (width - w) // 2, (height - h) // 2
    sx, sy = max(0, -ox), max(0, -oy)
    dx, dy = max(0, ox), max(0, oy)
    cw, ch = min(w - sx, width - dx), min(h - sy, height - dy)
    canvas[dy:dy + ch, dx:dx + cw] = image[sy:sy + ch, sx:sx + cw]
    if c == 4 and cc != 4:
        canvas[dy:dy + ch, dx:dx + cw, 3] = 1.0
    return canvas


def image_grayscale(image: ImageType, use_alpha: bool = False) -> ImageType:
    """Rec. 601 grey of a frame, ``(H, W, 1)``; optionally multiplied by its alpha."""
    if image.ndim == 2:
        image = image.unsqueeze(-1)
    if image.shape[2] == 1:
        return image
    out = gray(image[..., :3])
    if use_alpha and image.shape[2] == 4:
        out = out * image[..., 3:4]
    return out


def image_mask(image: ImageType, color: float = 0) -> ImageType:
    """A frame's alpha as ``(H, W)``, or a plane of ``color`` (0 to 255) when it has none."""
    if image.ndim == 3 and image.shape[2] == 4:
        return image[..., 3]
    return torch.full(image.shape[:2], float(color) / 255.0, dtype=image.dtype, device=image.device)


def image_mask_add(image: ImageType, mask: ImageType = None, alpha: float = 255) -> ImageType:
    """Return a frame as RGBA with ``mask`` as its alpha, resized to fit.

    Args:
        image: Frame.
        mask: New alpha; ``None`` keeps the frame's own, or ``alpha`` when it has none.
        alpha: Alpha, 0 to 255, for a frame with neither.

    Returns:
        The RGBA frame.
    """
    from .sample import resize

    image = image_convert(image, 4).clone()
    mask = image_mask(image, alpha) if mask is None else image_convert(mask, 1)
    if mask.ndim == 2:
        mask = mask.unsqueeze(-1)
    h, w = image.shape[:2]
    if mask.shape[:2] != (h, w):
        mask = resize(mask, w, h)
    image[..., 3] = mask[..., 0]
    return image


def image_mask_binary(image: ImageType) -> ImageType:
    """1 where a frame is not black (and, with alpha, not transparent), else 0; ``(H, W, 1)``."""
    if image.ndim == 2:
        image = image.unsqueeze(-1)
    level = image if image.shape[2] == 1 else gray(image[..., :3])
    if image.shape[2] == 4:
        level = level * (image[..., 3:4] > 0)
    return (level * 255.0 > 0.5).to(image.dtype)

# ==============================================================================
# === TENSORS AND PILLOW ===
# ==============================================================================

def to_frame(tensor: torch.Tensor, invert: bool = False, chan: int = 0) -> ImageType:
    """Turn one ComfyUI picture into a frame.

    Args:
        tensor: ``(H, W)``, ``(H, W, C)``, or a batch of one.
        invert: Invert the colour channels, leaving alpha.
        chan: Force 1, 3 or 4 channels; 0 keeps them.

    Returns:
        The frame, clipped to 0 to 1.

    Raises:
        ValueError: A batch of more than one picture was given.
    """
    frame = tensor.detach().float()
    if frame.ndim == 4:
        if frame.shape[0] != 1:
            raise ValueError("Expected one picture, got a batch.")
        frame = frame[0]
    if frame.ndim == 2:
        frame = frame.unsqueeze(-1)
    frame = frame.clamp(0, 1)
    if invert:
        if frame.shape[2] == 4:
            frame = torch.cat([1.0 - frame[..., :3], frame[..., 3:]], dim=2)
        else:
            frame = 1.0 - frame
    if chan > 0:
        frame = image_convert(frame, chan)
    return frame.contiguous()


def frame_tensor(image: ImageType, grayscale: bool = False) -> torch.Tensor:
    """A frame as a ComfyUI tensor; ``grayscale`` gives a ``(H, W)`` mask instead."""
    if image.ndim < 3:
        image = image.unsqueeze(-1)
    if grayscale:
        if image.shape[2] > 1:
            image = gray(image[..., :3])
        return image[..., 0].float().cpu().clone()
    return image.float().cpu().clone()


def frame_outputs(image: ImageType, matte: RGBA_Int = (0, 0, 0, 255)) -> tuple[torch.Tensor, ...]:
    """The ``(RGBA, RGB, MASK)`` tensors a picture node returns for one frame."""
    rgba = image_convert(image, 4, matte=matte).float().cpu()
    return rgba, rgba[..., :3].contiguous(), rgba[..., 3].contiguous()


def frame_to_pil(image: ImageType) -> Image.Image:
    """A frame as an 8-bit Pillow image."""
    if image.ndim == 3 and image.shape[2] == 1:
        image = image[..., 0]
    array = (image.detach().float().clamp(0, 1) * 255.0).round().to(torch.uint8).cpu().numpy()
    return Image.fromarray(np.ascontiguousarray(array))


def pil_to_frame(image: Image.Image) -> ImageType:
    """An 8-bit Pillow image (L, RGB or RGBA) as a frame."""
    array = np.asarray(image, dtype=np.uint8)
    frame = torch.from_numpy(array.astype(np.float32) / 255.0)
    return frame.unsqueeze(-1) if frame.ndim == 2 else frame


def tensor_to_pil(tensor: torch.Tensor) -> Image.Image:
    """One ComfyUI picture as an 8-bit Pillow image."""
    return frame_to_pil(to_frame(tensor))
