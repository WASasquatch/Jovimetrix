"""Composition helpers: blending, cropping, fitting, mirroring, stacking and transforms."""

from __future__ import annotations

import math
from typing import Optional

import torch

from ..enums import EnumBlendType, EnumEdge, EnumInterpolation, EnumMirrorMode, EnumOrientation, \
    EnumScaleMode

from . import PixelType, Coord2D_Float, ImageType, RGBA_Int

from .convert import image_convert, image_mask, image_mask_add

from .misc import image_minmax, image_by_size

from .pixel import pixel_convert

from .sample import resize, rotation_matrix, warp_affine

from .kernels import pad

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def _solid(width: int, height: int, color, channels: int = 4, like: ImageType = None) -> ImageType:
    """A ``(height, width, channels)`` frame of one 0 to 255 colour."""
    values = [float(c) / 255.0 for c in (tuple(color) if isinstance(color, (list, tuple)) else (color,))]
    values = (values + [values[-1]] * channels)[:channels]
    kw = {"dtype": like.dtype, "device": like.device} if like is not None else {}
    return torch.tensor(values, **kw).repeat(height, width, 1)


def image_blend(background: ImageType, foreground: ImageType, mask: Optional[ImageType] = None,
                blendOp: EnumBlendType = EnumBlendType.NORMAL, alpha: float = 1) -> ImageType:
    """Blend a foreground over a background with one of the blend modes.

    Args:
        background: Background frame; it sets the size.
        foreground: Foreground frame, centred on the background.
        mask: Where the foreground shows; its own alpha when ``None``. A mask given for a
            foreground that has alpha is limited by it.
        blendOp: Blend mode.
        alpha: Opacity of the foreground, 0 to 1.

    Returns:
        The RGBA result; its alpha is the mask used, unless the foreground was grey.
    """
    from .blend import blend_layers

    h, w = background.shape[:2]
    back = image_convert(background, 4, w, h)
    cc = foreground.shape[2] if foreground.ndim > 2 else 1
    fore = image_convert(foreground, 4, w, h).clone()
    old_mask = image_mask(fore)
    if mask is None:
        mask = old_mask
    else:
        mask = image_convert(mask, 1, w, h)[..., 0]
        if cc == 4:
            mask = torch.minimum(mask, old_mask)
    fore[..., 3] = mask
    image = blend_layers(back, fore, blendOp, float(min(1.0, max(0.0, alpha))))
    if cc != 1:
        image = image_mask_add(image, mask)
    return image


def _crop_box(image: ImageType, x1: int, y1: int, x2: int, y2: int) -> ImageType:
    """The pixels from ``(x1, y1)`` to ``(x2, y2)``, both included."""
    if image.ndim == 2:
        image = image.unsqueeze(-1)
    return image[y1:y2 + 1, x1:x2 + 1].clone()


def image_crop(image: ImageType, width: int = None, height: int = None,
               offset: tuple[float, float] = (0, 0)) -> ImageType:
    """Cut a ``width`` by ``height`` window whose top left corner sits at ``offset``.

    Args:
        image: Frame.
        width: Window width; the frame width when ``None``.
        height: Window height; the frame height when ``None``.
        offset: Corner position. 0 to 1 is a fraction of the frame; above 1 is pixels.

    Returns:
        The cropped frame.
    """
    h, w = image.shape[:2]
    width = w if width is None else int(width)
    height = h if height is None else int(height)
    ox, oy = offset
    x = int(ox * w) if abs(ox) <= 1 else int(ox)
    y = int(oy * h) if abs(oy) <= 1 else int(oy)
    x = max(0, min(w - 1, x))
    y = max(0, min(h - 1, y))
    x2 = max(x, min(w - 1, x + width - 1))
    y2 = max(y, min(h - 1, y + height - 1))
    return _crop_box(image, x, y, x2, y2)


def image_crop_center(image: ImageType, width: int = None, height: int = None) -> ImageType:
    """Cut a ``width`` by ``height`` window around the centre, clipped to the frame."""
    h, w = image.shape[:2]
    cx, cy = w // 2, h // 2
    width = w if width is None else width
    height = h if height is None else height
    x1 = max(0, int(cx - width // 2))
    y1 = max(0, int(cy - height // 2))
    x2 = min(w, int(cx + width // 2)) - 1
    y2 = min(h, int(cy + height // 2)) - 1
    return _crop_box(image, x1, y1, max(x1, x2), max(y1, y2))


def image_crop_polygonal(image: ImageType, points: list[Coord2D_Float]) -> ImageType:
    """Cut out a polygon: the box around it, black outside the polygon; alpha is kept.

    Args:
        image: Frame, or a ``(H, W)`` plane.
        points: Corners in pixels.

    Returns:
        The cropped frame.
    """
    import numpy as np
    from PIL import Image, ImageDraw

    if image.ndim == 2:
        image = image.unsqueeze(-1)
    height, width, cc = image.shape
    canvas = Image.new("L", (width, height), 0)
    ImageDraw.Draw(canvas).polygon([(int(x), int(y)) for x, y in points], fill=255, outline=255)
    inside = torch.from_numpy(np.array(canvas) > 0)
    rows = torch.nonzero(inside.any(dim=1)).flatten()
    cols = torch.nonzero(inside.any(dim=0)).flatten()
    if rows.numel() == 0 or cols.numel() == 0:
        return image.clone()
    y1, y2 = int(rows[0]), int(rows[-1])
    x1, x2 = int(cols[0]), int(cols[-1])
    crop = image[y1:y2 + 1, x1:x2 + 1]
    keep = inside[y1:y2 + 1, x1:x2 + 1].to(device=image.device, dtype=image.dtype).unsqueeze(-1)
    if cc == 4:
        return image_mask_add(crop[..., :3] * keep, crop[..., 3])
    return crop * keep


def image_edge_wrap(image: ImageType, tileX: float = 1., tileY: float = 1.,
                    edge: EnumEdge = EnumEdge.WRAP) -> ImageType:
    """Surround a frame with copies of itself, ``tileX`` and ``tileY`` of its size each side."""
    height, width = image.shape[:2]
    tx = max(0, int(width * tileX)) if edge in (EnumEdge.WRAP, EnumEdge.WRAPX) else 0
    ty = max(0, int(height * tileY)) if edge in (EnumEdge.WRAP, EnumEdge.WRAPY) else 0
    return pad(image, ty, ty, tx, tx, "wrap")


def _shift(image: ImageType, dx: float, dy: float, width: int, height: int) -> ImageType:
    """Move a frame by whole or fractional pixels onto a transparent canvas."""
    if float(dx).is_integer() and float(dy).is_integer():
        dx, dy = int(dx), int(dy)
        out = torch.zeros((height, width, image.shape[2]), dtype=image.dtype, device=image.device)
        h, w = image.shape[:2]
        sx, sy = max(0, -dx), max(0, -dy)
        tx, ty = max(0, dx), max(0, dy)
        cw, ch = min(w - sx, width - tx), min(h - sy, height - ty)
        if cw > 0 and ch > 0:
            out[ty:ty + ch, tx:tx + cw] = image[sy:sy + ch, sx:sx + cw]
        return out
    return warp_affine(image, [[1, 0, dx], [0, 1, dy]], width, height)


def image_flatten(image: list[ImageType], offsetX: int = None, offsetY: int = None,
                  width: int = None, height: int = None, mode=EnumScaleMode.MATTE,
                  sample: EnumInterpolation = EnumInterpolation.LANCZOS4) -> ImageType:
    """Add frames together on one RGBA canvas, each optionally fitted and offset.

    Args:
        image: Frames.
        offsetX: Horizontal offset in pixels.
        offsetY: Vertical offset in pixels.
        width: Canvas width when not MATTE.
        height: Canvas height when not MATTE.
        mode: How each frame fits the canvas; MATTE sizes the canvas to the largest frame.
        sample: Resampling.

    Returns:
        The RGBA sum, clipped to 1.
    """
    if mode == EnumScaleMode.MATTE:
        width, height = image_minmax(image)[2:]
    else:
        h, w = image[0].shape[:2]
        width = width or w
        height = height or h

    current = torch.zeros((height, width, 4), dtype=image[0].dtype, device=image[0].device)
    for x in image:
        if mode not in (EnumScaleMode.MATTE, EnumScaleMode.RESIZE_MATTE):
            x = image_scalefit(x, width, height, mode, sample)
        x = image_matte(x, (0, 0, 0, 0), width, height)
        x = _shift(x, offsetX or 0, offsetY or 0, width, height)
        x = image_scalefit(x, width, height, EnumScaleMode.CROP, sample)
        current = (current + image_convert(x, 4)).clamp(0, 1)
    return current


def image_levels(image: ImageType, in_low=0.0, in_mid=0.5, in_high=1.0, out_low=0.0, out_high=1.0) -> ImageType:
    """Levels: input black, mid and white points, then output black and white; alpha is kept.

    Args:
        image: Frame.
        in_low: Input black point, 0 to 1.
        in_mid: Input midtone; 0.5 leaves midtones alone.
        in_high: Input white point.
        out_low: Output black.
        out_high: Output white.

    Returns:
        The adjusted frame.
    """
    alpha = image[..., 3:] if image.shape[2] == 4 else None
    rgb = image[..., :3] if alpha is not None else image
    rgb = ((rgb - in_low) / max(in_high - in_low, 1e-6)).clamp(0, 1)
    in_mid = min(max(in_mid, 1e-6), 1 - 1e-6)
    rgb = rgb ** (math.log(0.5) / math.log(in_mid))
    rgb = (rgb * (out_high - out_low) + out_low).clamp(0, 1)
    return rgb if alpha is None else torch.cat([rgb, alpha], dim=2)


def image_matte(image: ImageType, color: RGBA_Int = (0, 0, 0, 255),
                width: int = None, height: int = None) -> ImageType:
    """Lay a frame, centred, over a solid matte; an RGBA frame keeps its alpha.

    Args:
        image: Frame.
        color: Matte RGBA, 0 to 255.
        width: Matte width; the frame width when ``None``.
        height: Matte height; the frame height when ``None``.

    Returns:
        The RGBA frame. A frame larger than the matte is cut to it around the centre.
    """
    if image.ndim == 2:
        image = image.unsqueeze(-1)
    ih, iw = image.shape[:2]
    width = width or iw
    height = height or ih
    matte = _solid(width, height, color, 4, image)
    ox, oy = (width - iw) // 2, (height - ih) // 2
    sx, sy = max(0, -ox), max(0, -oy)
    tx, ty = max(0, ox), max(0, oy)
    cw, ch = min(iw - sx, width - tx), min(ih - sy, height - ty)
    if cw <= 0 or ch <= 0:
        return matte
    part = image[sy:sy + ch, sx:sx + cw]
    region = matte[ty:ty + ch, tx:tx + cw]
    if part.shape[2] == 4:
        a = part[..., 3:4]
        region[..., :3] = (1 - a) * region[..., :3] + a * part[..., :3]
        region[..., 3] = part[..., 3]
    else:
        region[..., :3] = part[..., :3] if part.shape[2] >= 3 else part.expand(-1, -1, 3)
    return matte


def image_mirror(image: ImageType, mode: EnumMirrorMode, x: float = 0.5, y: float = 0.5) -> ImageType:
    """Mirror one half of a frame onto the other about a pivot.

    Args:
        image: Frame.
        mode: Axes to mirror, and which side is kept.
        x: Horizontal pivot, 0 to 1.
        y: Vertical pivot, 0 to 1.

    Returns:
        The mirrored frame.
    """
    if image.ndim == 2:
        image = image.unsqueeze(-1)
    height, width = image.shape[:2]

    def mirror(img: ImageType, axis: int, reverse: bool = False) -> ImageType:
        pivot = min(1.0, max(0.0, x if axis == 1 else y))
        flip = img.flip(1 if axis == 1 else 0)
        if reverse:
            pivot = 1. - pivot
            flip, img = img, flip
        scalar = height if axis == 0 else width
        slice1 = int(pivot * scalar)
        slice1w = scalar - slice1
        slice2w = min(scalar - slice1w, slice1w)
        output = torch.zeros_like(img)
        if axis == 0:
            output[:slice1] = img[:slice1]
            output[slice1:slice1 + slice2w] = flip[slice1w:slice1w + slice2w]
        else:
            output[:, :slice1] = img[:, :slice1]
            output[:, slice1:slice1 + slice2w] = flip[:, slice1w:slice1w + slice2w]
        return output

    if mode in (EnumMirrorMode.X, EnumMirrorMode.FLIP_X, EnumMirrorMode.XY, EnumMirrorMode.FLIP_XY,
                EnumMirrorMode.X_FLIP_Y, EnumMirrorMode.FLIP_X_FLIP_Y):
        reverse = mode in (EnumMirrorMode.FLIP_X, EnumMirrorMode.FLIP_XY, EnumMirrorMode.FLIP_X_FLIP_Y)
        image = mirror(image, 1, reverse)
    if mode not in (EnumMirrorMode.NONE, EnumMirrorMode.X, EnumMirrorMode.FLIP_X):
        reverse = mode in (EnumMirrorMode.FLIP_Y, EnumMirrorMode.FLIP_X_FLIP_Y, EnumMirrorMode.X_FLIP_Y)
        image = mirror(image, 0, reverse)
    return image


def image_resize(image: ImageType, width: int, height: int,
                 sample: EnumInterpolation = EnumInterpolation.LANCZOS4) -> ImageType:
    """Resize to ``width`` by ``height``."""
    return resize(image, width, height, sample)


def image_rotate(image: ImageType, angle: float, center: Coord2D_Float = (0.5, 0.5),
                 edge: EnumEdge = EnumEdge.CLIP) -> ImageType:
    """Rotate clockwise by ``angle`` degrees about a point given as fractions of the frame.

    Args:
        image: Frame.
        angle: Degrees, clockwise.
        center: Pivot as fractions of the frame.
        edge: CLIP leaves the corners empty; the WRAP modes fill them with tiled copies.

    Returns:
        The rotated frame, the same size.
    """
    h, w = image.shape[:2]
    if edge != EnumEdge.CLIP:
        image = image_edge_wrap(image, edge=edge)
    height, width = image.shape[:2]
    pivot = (int(width * center[0]), int(height * center[1]))
    image = warp_affine(image, rotation_matrix(pivot, -angle, 1.0), width, height)
    if edge != EnumEdge.CLIP:
        image = image_crop_center(image, w, h)
    return image


def image_scale(image: ImageType, scale: Coord2D_Float = (1.0, 1.0),
                sample: EnumInterpolation = EnumInterpolation.LANCZOS4,
                edge: EnumEdge = EnumEdge.CLIP) -> ImageType:
    """Scale by ``(sx, sy)``; the WRAP modes tile first and cut back to the original size."""
    h, w = image.shape[:2]
    if edge != EnumEdge.CLIP:
        image = image_edge_wrap(image, edge=edge)
    height, width = image.shape[:2]
    image = resize(image, max(1, int(width * scale[0])), max(1, int(height * scale[1])), sample)
    if edge != EnumEdge.CLIP:
        image = image_crop_center(image, w, h)
    return image


def image_scalefit(image: ImageType, width: int, height: int,
                   mode: EnumScaleMode = EnumScaleMode.MATTE,
                   sample: EnumInterpolation = EnumInterpolation.LANCZOS4,
                   matte: PixelType = (0, 0, 0, 0)) -> ImageType:
    """Fit a frame to ``width`` by ``height``.

    Args:
        image: Frame.
        width: Target width.
        height: Target height.
        mode: MATTE centres it on a matte; RESIZE_MATTE grows the canvas to fit, then crops;
            ASPECT and ASPECT_SHORT scale to the long or short side; CROP cuts the centre;
            FIT stretches.
        sample: Resampling.
        matte: Matte RGBA, 0 to 255.

    Returns:
        The fitted frame.
    """
    match mode:
        case EnumScaleMode.MATTE:
            image = image_matte(image, matte, width, height)

        case EnumScaleMode.RESIZE_MATTE:
            h, w = image.shape[:2]
            w2, h2 = max(width, w), max(height, h)
            canvas = _solid(w2, h2, matte, 4, image)
            image = image_blend(canvas, image_matte(image, (0, 0, 0, 0), w2, h2))
            image = image_crop_center(image, width, height)

        case EnumScaleMode.ASPECT:
            h, w = image.shape[:2]
            ratio = max(width, height) / max(w, h)
            image = resize(image, max(1, round(w * ratio)), max(1, round(h * ratio)), sample, ratio)

        case EnumScaleMode.ASPECT_SHORT:
            h, w = image.shape[:2]
            ratio = min(width, height) / min(w, h)
            image = resize(image, max(1, round(w * ratio)), max(1, round(h * ratio)), sample, ratio)

        case EnumScaleMode.CROP:
            h, w = image.shape[:2]
            if h < height or w < width:
                image = image_scalefit(image, width, height, EnumScaleMode.RESIZE_MATTE, sample, matte)
            image = image_crop_center(image, width, height)

        case EnumScaleMode.FIT:
            image = resize(image, width, height, sample)
    return image


def image_split(image: ImageType) -> tuple[ImageType, ...]:
    """Red, green, blue and alpha planes, each ``(H, W, 1)``; alpha is 1 when absent."""
    if image.ndim == 2:
        image = image.unsqueeze(-1)
    a = torch.ones_like(image[..., :1])
    if image.shape[2] == 1:
        return image, image, image, a
    if image.shape[2] == 4:
        a = image[..., 3:4]
    return image[..., 0:1], image[..., 1:2], image[..., 2:3], a


def image_stacker(image_list: list[ImageType], axis: EnumOrientation = EnumOrientation.HORIZONTAL,
                  stride: int = 0, matte: PixelType = (0, 0, 0, 255)) -> ImageType:
    """Lay frames out in a row, a column or a grid, each centred in a cell of the largest size.

    Args:
        image_list: Frames.
        axis: HORIZONTAL, VERTICAL or GRID.
        stride: Cells per grid row; 0 makes the grid about square.
        matte: Cell and filler RGBA, 0 to 255.

    Returns:
        The RGBA layout.
    """
    _, width, height = image_by_size(image_list)
    images = [image_matte(image_convert(i, 4), matte, width, height) for i in image_list]
    count = len(images)
    matte = pixel_convert(matte, 4)
    match axis:
        case EnumOrientation.GRID:
            if stride < 1:
                stride = int(math.ceil(math.sqrt(count)))
            stride = max(1, min(stride, count))
            rows = [torch.cat(images[i:i + stride], dim=1) for i in range(0, count, stride)]
            overhang = count % stride
            if overhang:
                filler = _solid((stride - overhang) * width, height, matte, 4, images[0])
                rows[-1] = torch.cat([rows[-1], filler], dim=1)
            return torch.cat(rows, dim=0)
        case EnumOrientation.VERTICAL:
            return torch.cat(images, dim=0)
    return torch.cat(images, dim=1)


def image_translate(image: ImageType, offset: Coord2D_Float = (0.0, 0.0), edge: EnumEdge = EnumEdge.CLIP,
                    border_value: int = 0) -> ImageType:
    """Move a frame by fractions of its size; CLIP leaves the gap empty, the WRAP modes wrap.

    Args:
        image: Frame.
        offset: ``(x, y)`` as fractions of the width and height.
        edge: Edge handling.
        border_value: Fill for CLIP, 0 to 255.

    Returns:
        The moved frame, the same size.
    """
    height, width = image.shape[:2]
    matrix = [[1, 0, offset[0] * width], [0, 1, offset[1] * height]]
    border = "constant" if edge == EnumEdge.CLIP else "wrap"
    return warp_affine(image, matrix, width, height, border, float(border_value) / 255.0)


def image_transform(image: ImageType, offset: Coord2D_Float = (0.0, 0.0), angle: float = 0,
                    scale: Coord2D_Float = (1.0, 1.0),
                    sample: EnumInterpolation = EnumInterpolation.LANCZOS4,
                    edge: EnumEdge = EnumEdge.CLIP) -> ImageType:
    """Scale (a negative scale flips), rotate, then move a frame.

    Args:
        image: Frame.
        offset: Move as fractions of the frame.
        angle: Degrees, clockwise.
        scale: ``(sx, sy)``.
        sample: Resampling for the scale.
        edge: Edge handling.

    Returns:
        The transformed frame.
    """
    sx, sy = scale
    if sx < 0:
        image = image.flip(1)
        sx = -sx
    if sy < 0:
        image = image.flip(0)
        sy = -sy
    if sx != 1. or sy != 1.:
        image = image_scale(image, (sx, sy), sample, edge)
    if angle != 0:
        image = image_rotate(image, angle, edge=edge)
    if offset[0] != 0. or offset[1] != 0.:
        image = image_translate(image, offset, edge)
    return image
