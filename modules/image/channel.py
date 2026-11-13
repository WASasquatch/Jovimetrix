"""Channel operations: solid fills, merging planes and swapping channels between images."""

import numpy as np

from ..params import \
    IMAGE_SIZE_MIN

from ..enums import \
    EnumImageType, EnumPixelSwizzle, EnumScaleMode

from . import \
    PixelType, ImageType

from .convert import \
    image_convert

from .compose import \
    image_scalefit, image_matte

from .pixel import \
    pixel_eval

# ==============================================================================
# === CHANNEL ===
# ==============================================================================

def channel_add(image:ImageType, color:PixelType=255) -> ImageType:
    """Append a channel of one solid level to an image.

    Args:
        image: Input image.
        color: Level of the new channel, 0 to 255.

    Returns:
        The image with one more channel.
    """
    h, w = image.shape[:2]
    color = pixel_eval(color, EnumImageType.GRAYSCALE)
    new = channel_solid(w, h, color, EnumImageType.GRAYSCALE)
    return np.concatenate([image, new], axis=-1)

def channel_solid(width:int=IMAGE_SIZE_MIN, height:int=IMAGE_SIZE_MIN, color:PixelType=(0, 0, 0, 255),
                chan:EnumImageType=EnumImageType.RGB) -> ImageType:
    """Build an image of one solid colour.

    Args:
        width: Width in pixels.
        height: Height in pixels.
        color: Level or RGB(A) colour, 0 to 255.
        chan: Channel layout of the result.

    Returns:
        The image, ``uint8``.
    """
    if chan == EnumImageType.GRAYSCALE:
        color = pixel_eval(color, EnumImageType.GRAYSCALE)
        return np.full((height, width, 1), color, dtype=np.uint8)

    if not isinstance(color, (list, set, tuple)):
        color = [color]
    color = tuple(color) + (0,) * (3 - len(color))
    if chan in [EnumImageType.BGR, EnumImageType.RGB]:
        if chan == EnumImageType.BGR:
            color = color[2::-1]
        return np.full((height, width, 3), color[:3], dtype=np.uint8)

    if len(color) < 4:
        color += (255,)

    if chan == EnumImageType.BGRA:
        color = tuple(color[2::-1]) + (color[3],)
    return np.full((height, width, 4), color[:4], dtype=np.uint8)

def channel_merge(channels: list[ImageType]) -> ImageType:
    """Stack single-channel planes into one image, centring planes of differing size.

    Args:
        channels: One plane per output channel; ``None`` leaves that channel black.

    Returns:
        The merged image.
    """
    max_height = max(ch.shape[0] for ch in channels if ch is not None)
    max_width = max(ch.shape[1] for ch in channels if ch is not None)
    num_channels = len(channels)
    dtype = next(ch.dtype for ch in channels if ch is not None)
    output = np.zeros((max_height, max_width, num_channels), dtype=dtype)

    for i, channel in enumerate(channels):
        if channel is None:
            continue

        h, w = channel.shape[:2]
        if channel.ndim == 3 and channel.shape[2] == 1:
            channel = channel[:, :, 0]

        pad_top = (max_height - h) // 2
        pad_bottom = max_height - h - pad_top
        pad_left = (max_width - w) // 2
        pad_right = max_width - w - pad_left
        padded_channel = np.pad(channel, ((pad_top, pad_bottom), (pad_left, pad_right)),
                                mode='constant', constant_values=0)
        output[..., i] = padded_channel

    if num_channels == 1:
        output = output[..., 0]
    return output

def channel_swap(imgA:ImageType, imgB:ImageType,
                  swap_in:tuple[EnumPixelSwizzle, ...],
                  matte:tuple[int,...]=(0,0,0,255)) -> ImageType:
    """Build an RGBA image whose channels each come from image A, image B or a constant.

    Args:
        imgA: Image A.
        imgB: Image B, fitted to A's size.
        swap_in: Source of the red, green, blue and alpha channels, in that order.
        matte: RGBA constant used by a ``CONSTANT`` source, 0 to 255.

    Returns:
        The RGBA image.
    """
    imgA = image_convert(imgA, 4)
    h,w = imgA.shape[:2]

    imgB = image_convert(imgB, 4)
    imgB = image_matte(imgB, (0,0,0,0), w, h)
    imgB = image_scalefit(imgB, w, h, EnumScaleMode.CROP)

    out = channel_solid(w, h, tuple(matte), EnumImageType.RGBA)
    for target_idx, swap in enumerate(swap_in):
        if swap != EnumPixelSwizzle.CONSTANT:
            source_idx = swap.value // 10
            source = [imgA, imgB][swap.value % 10]
            out[:,:,target_idx] = source[:,:,source_idx]
    return out
