"""Text measured and drawn onto RGBA frames."""

import textwrap

from PIL import Image, ImageFont, ImageDraw

from ..enums import \
    EnumAlignment, EnumJustify

from .. import fonts

from . import \
    PixelType, ImageType

#: Largest font size ``text_autosize`` tries, in pixels.
MAX_FONT_SIZE = 4096

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def text_size(draw: ImageDraw.ImageDraw, text:str, font:ImageFont.ImageFont) -> tuple[int, int]:
    """Measure text drawn with a font.

    Args:
        draw: A drawing context.
        text: The text.
        font: The font.

    Returns:
        ``(width, height)`` in pixels.
    """
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def text_autosize(text:str, font:str, width:int, height:int, columns:int=0) -> tuple[str, float, int, int]:
    """Find the font size at which text first reaches the edge of a box.

    Args:
        text: The text.
        font: Font menu name.
        width: Box width.
        height: Box height.
        columns: Wrap lines at this many characters; 0 keeps the text as written.

    Returns:
        ``(text, size, width, height)``: the wrapped text, a third of the fitting size, and
        the measured size of the text at that size.
    """
    img = Image.new("L", (max(1, width), max(1, height)))
    draw = ImageDraw.Draw(img)
    if columns != 0:
        lines = []
        for x in text.split('\n'):
            lines.extend(textwrap.wrap(x, columns, break_long_words=False))
        text = '\n'.join(lines)

    test_text = text if columns == 0 else ' ' * columns

    def reaches(size: int) -> tuple[bool, int, int]:
        w, h = text_size(draw, test_text, fonts.load(font, size))
        return (w >= width or h >= height), w, h

    lo, hi = 1, MAX_FONT_SIZE
    while lo < hi:
        mid = (lo + hi) // 2
        if reaches(mid)[0]:
            hi = mid
        else:
            lo = mid + 1
    _, w, h = reaches(lo)
    return text, lo * 0.33, w, h

def text_draw(full_text: str, font: ImageFont.ImageFont,
              width: int, height: int,
              align: EnumAlignment=EnumAlignment.CENTER,
              justify: EnumJustify=EnumJustify.CENTER,
              margin: int=0, line_spacing: int=0,
              color: PixelType=(255,255,255,255)) -> ImageType:
    """Draw text on a transparent canvas.

    Args:
        full_text: The text; ``\\n`` starts a line.
        font: The font.
        width: Canvas width.
        height: Canvas height.
        align: Vertical placement.
        justify: Horizontal placement of each line.
        margin: Space kept from the canvas edges, in pixels.
        line_spacing: Extra space between lines, in pixels.
        color: RGBA colour of the letters.

    Returns:
        The RGBA image.
    """
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)
    text_lines = full_text.split('\n')
    count = len(text_lines)
    height_max = text_size(draw, full_text, font)[1] + line_spacing * (count-1)
    height_delta = height_max / count

    if align == EnumAlignment.TOP:
        y = margin
    elif align == EnumAlignment.BOTTOM:
        y = height - height_max * 1.5 - margin
    else:
        y = height * 0.5 - height_max

    fill = tuple(int(c) for c in color)
    for line in text_lines:
        line_width = text_size(draw, line, font)[0]
        if justify == EnumJustify.LEFT:
            x = margin
        elif justify == EnumJustify.RIGHT:
            x = width - line_width - margin
        else:
            x = (width - line_width) / 2
        draw.text((x, y), line, fill=fill, font=font)
        y += height_delta
    from .convert import pil_to_frame

    return pil_to_frame(img)
