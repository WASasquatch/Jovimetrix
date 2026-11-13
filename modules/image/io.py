"""Reading images from disk or, when the settings allow it, from a web address."""

import urllib.request

import cv2
import numpy as np
from PIL import Image, ImageOps

from .. import config, log

from . import \
    ImageType

from .convert import \
    image_mask

logger = log.get_logger("image.io")

#: Largest download read from a web address, in bytes.
MAX_DOWNLOAD = 64 * 1024 * 1024

#: Seconds to wait for a web address.
TIMEOUT = 20

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def to_uint8(img: np.ndarray) -> np.ndarray:
    """Scale an image of any bit depth to ``uint8`` without stretching its levels.

    Args:
        img: Image array.

    Returns:
        The ``uint8`` image.
    """
    if img.dtype == np.uint8:
        return img
    if img.dtype == np.uint16:
        return (img.astype(np.uint32) // 257).astype(np.uint8)
    if np.issubdtype(img.dtype, np.floating):
        return np.clip(img * 255.0, 0, 255).round().astype(np.uint8)
    if img.dtype == bool:
        return img.astype(np.uint8) * 255
    return np.clip(img, 0, 255).astype(np.uint8)

def _decoded(img: np.ndarray) -> np.ndarray:
    """Turn an OpenCV decode (BGR or BGRA) into an RGB or RGBA ``uint8`` array."""
    img = to_uint8(img)
    if img.ndim == 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        elif img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        img = np.expand_dims(img, -1)
    return img

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

def image_load(url: str) -> tuple[ImageType, ImageType]:
    """Read an image from a resolved local path or a web address.

    Args:
        url: A path already checked by the sandbox, or an ``http(s)`` address.

    Returns:
        ``(image, mask)``: RGB(A) ``uint8`` image and its alpha, or a black mask.

    Raises:
        PermissionError: A web address was given and fetching is off.
        ValueError: Nothing readable is at the path.
    """
    if url.lower().startswith(("http://", "https://")):
        data = np.frombuffer(_download(url), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError("The web address did not return an image Jovimetrix can read.")
        img = _decoded(img)
    else:
        img = cv2.imread(url, cv2.IMREAD_UNCHANGED)
        if img is not None:
            img = _decoded(img)
        else:
            try:
                with Image.open(url) as pil:
                    pil = ImageOps.exif_transpose(pil)
                    if pil.mode not in ("L", "RGB", "RGBA"):
                        pil = pil.convert("RGBA" if "A" in pil.getbands() else "RGB")
                    img = to_uint8(np.array(pil))
            except Exception as error:
                raise ValueError(f"The file could not be read as an image ({type(error).__name__}).") from error
            if img.ndim == 2:
                img = np.expand_dims(img, -1)

    return img, image_mask(img)
