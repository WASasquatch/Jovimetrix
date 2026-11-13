"""Conversion of a single colour between channel layouts and precisions."""

import numpy as np

from ..enums import \
    EnumImageType, EnumGrayscaleCrunch, EnumPrecision

from . import \
    PixelType

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def pixel_convert(color:PixelType, size:int=4, alpha:int=255) -> PixelType:
    """Pad or cut a colour to ``size`` components.

    Args:
        color: The colour.
        size: Components wanted: 1, 3 or 4.
        alpha: Alpha added when growing to four components.

    Returns:
        The colour; a scalar when ``size`` is 1 or 2.
    """
    color = tuple(color)
    if (cc := len(color)) == size:
        return color
    if size > 2:
        color += (0,) * (3 - cc)
        if size == 4:
            color += (alpha,)
        return color[:size]
    return color[0]

def pixel_eval(color: PixelType,
            target: EnumImageType=EnumImageType.RGBA,
            precision:EnumPrecision=EnumPrecision.INT,
            crunch:EnumGrayscaleCrunch=EnumGrayscaleCrunch.MEAN) -> tuple[PixelType] | PixelType:
    """Read a colour in 0 to 255, or 0 to 1 for floats, into a target layout.

    Args:
        color: Level or colour.
        target: Layout of the result.
        precision: Integers in 0 to 255 or floats in 0 to 1.
        crunch: How several channels collapse to one grey level.

    Returns:
        A tuple, or a scalar for a greyscale target.
    """

    def parse_single_color(c: PixelType) -> PixelType:
        if not isinstance(c, (int, np.integer)):
            c = float(np.clip(c, 0, 1))
            if precision == EnumPrecision.INT:
                c = int(c * 255)
        else:
            c = int(np.clip(c, 0, 255))
            if precision == EnumPrecision.FLOAT:
                c /= 255
        return c

    if isinstance(color, (float, int, np.integer, np.floating)):
        color = tuple([parse_single_color(color)])
    elif isinstance(color, (set, tuple, list)):
        color = tuple([parse_single_color(c) for c in color])

    if target == EnumImageType.GRAYSCALE:
        alpha = 1
        if len(color) > 3:
            alpha = color[3]
            if precision == EnumPrecision.INT:
                alpha /= 255
            color = color[:3]
        match crunch:
            case EnumGrayscaleCrunch.LOW:
                val = min(color) * alpha
            case EnumGrayscaleCrunch.HIGH:
                val = max(color) * alpha
            case _:
                val = np.mean(color) * alpha
        if precision == EnumPrecision.INT:
            val = int(val)
        return val

    if len(color) < 3:
        color += (0,) * (3 - len(color))

    if target in [EnumImageType.RGB, EnumImageType.BGR]:
        color = color[:3]
        if target == EnumImageType.BGR:
            color = color[::-1]
        return color

    if len(color) < 4:
        color += (255,)

    if target == EnumImageType.BGRA:
        color = tuple(color[2::-1]) + tuple([color[-1]])
    return color

def pixel_hsv_adjust(color:PixelType, hue:int=0, saturation:int=0, value:int=0,
                     mod_color:bool=True, mod_sat:bool=False,
                     mod_value:bool=False) -> PixelType:
    """Shift an OpenCV HSV colour, H in 0 to 179 and S, V in 0 to 255.

    Args:
        color: The HSV colour.
        hue: Hue shift.
        saturation: Saturation shift.
        value: Value shift.
        mod_color: Wrap the hue rather than clipping it.
        mod_sat: Wrap the saturation rather than clipping it.
        mod_value: Wrap the value rather than clipping it.

    Returns:
        The shifted colour as a list.
    """
    h, s, v = (float(c) for c in color[:3])
    hsv = [0.0, 0.0, 0.0]
    hsv[0] = (h + hue) % 180 if mod_color else float(np.clip(h + hue, 0, 180))
    hsv[1] = (s + saturation) % 255 if mod_sat else float(np.clip(s + saturation, 0, 255))
    hsv[2] = (v + value) % 255 if mod_value else float(np.clip(v + value, 0, 255))
    return hsv
