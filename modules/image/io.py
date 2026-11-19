"""Reading images from disk.

Jovimetrix never downloads anything. Like ComfyUI's own Load Image, it reads pictures only from
paths the sandbox has already resolved inside ComfyUI's folders or the folders in ``allow_read``.
"""

from __future__ import annotations

import numpy as np
import torch

from .. import log

from . import ImageType

from .convert import image_mask

logger = log.get_logger("image.io")

#: Prefixes of the web addresses Jovimetrix refuses to treat as paths.
WEB_PREFIXES = ("http://", "https://", "ftp://", "ftps://", "file://")

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def to_unit(img: np.ndarray, mode: str = "") -> np.ndarray:
    """Scale an image array of any bit depth to ``float32`` in 0 to 1, without stretching levels.

    Args:
        img: Image array.
        mode: Pillow mode it came from; 16-bit modes are read as 16-bit.

    Returns:
        The array in 0 to 1.
    """
    if img.dtype == bool:
        return img.astype(np.float32)
    if img.dtype == np.uint8:
        return img.astype(np.float32) / 255.0
    if img.dtype == np.uint16 or mode.startswith("I;16"):
        return np.clip(img.astype(np.float32) / 65535.0, 0, 1)
    if np.issubdtype(img.dtype, np.floating):
        return np.clip(img.astype(np.float32), 0, 1)
    peak = 65535.0 if img.max(initial=0) > 255 else 255.0
    return np.clip(img.astype(np.float32) / peak, 0, 1)


def is_web_address(text: str) -> bool:
    """Return whether ``text`` is a web address rather than a path.

    Args:
        text: An entry as typed.

    Returns:
        True for ``http``, ``https``, ``ftp``, ``ftps`` and ``file`` addresses.
    """
    return text.strip().lower().startswith(WEB_PREFIXES)


def _decode(source) -> np.ndarray:
    """Open ``source`` with Pillow, honouring EXIF rotation; returns ``(H, W, C)`` in 0 to 1."""
    from PIL import Image, ImageOps

    with Image.open(source) as pil:
        pil = ImageOps.exif_transpose(pil)
        mode = pil.mode
        if mode in ("I", "I;16", "I;16B", "I;16L", "F"):
            img = to_unit(np.array(pil), mode)
        else:
            if mode not in ("L", "RGB", "RGBA"):
                pil = pil.convert("RGBA" if "A" in pil.getbands() or "transparency" in pil.info else "RGB")
            img = to_unit(np.array(pil))
    return img[..., None] if img.ndim == 2 else img


def image_load(path: str) -> tuple[ImageType, ImageType]:
    """Read an image from a local path the sandbox has resolved.

    Args:
        path: A path already checked by ``sandbox.resolve_read``.

    Returns:
        ``(frame, mask)``: the frame and its alpha, or a black mask when it has none.

    Raises:
        ValueError: ``path`` is a web address, or nothing readable is at it.
    """
    if is_web_address(path):
        raise ValueError("Jovimetrix reads pictures from ComfyUI's folders and does not download "
                         "web addresses.")
    try:
        img = _decode(path)
    except Exception as error:
        raise ValueError(f"The file could not be read as an image Jovimetrix can read "
                         f"({type(error).__name__}).") from error
    frame = torch.from_numpy(np.ascontiguousarray(img))
    return frame, image_mask(frame)
