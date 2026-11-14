"""Reading images from disk or, when the settings allow it, from a web address."""

from __future__ import annotations

import io
import urllib.request

import numpy as np
import torch

from .. import config, log

from . import ImageType

from .convert import image_mask

logger = log.get_logger("image.io")

#: Largest download read from a web address, in bytes.
MAX_DOWNLOAD = 64 * 1024 * 1024

#: Seconds to wait for a web address.
TIMEOUT = 20

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


def _download(url: str) -> bytes:
    if not config.get("allow_network"):
        raise PermissionError(
            "Jovimetrix does not fetch web addresses unless allow_network is true in "
            "ComfyUI/user/jovimetrix/config.json. Download the file into ComfyUI's input "
            "folder, or turn allow_network on."
        )
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Only http and https addresses can be fetched.")
    request = urllib.request.Request(url, headers={"User-Agent": "Jovimetrix"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError(f"The address returned more than {MAX_DOWNLOAD // (1024 * 1024)} MB.")
    return data


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


def image_load(url: str) -> tuple[ImageType, ImageType]:
    """Read an image from a resolved local path or a web address.

    Args:
        url: A path already checked by the sandbox, or an ``http(s)`` address.

    Returns:
        ``(frame, mask)``: the frame and its alpha, or a black mask when it has none.

    Raises:
        PermissionError: A web address was given and fetching is off.
        ValueError: Nothing readable is at the path.
    """
    remote = url.lower().startswith(("http://", "https://"))
    source = io.BytesIO(_download(url)) if remote else url
    try:
        img = _decode(source)
    except Exception as error:
        what = "web address did not return" if remote else "file could not be read as"
        raise ValueError(f"The {what} an image Jovimetrix can read ({type(error).__name__}).") from error
    frame = torch.from_numpy(np.ascontiguousarray(img))
    return frame, image_mask(frame)
