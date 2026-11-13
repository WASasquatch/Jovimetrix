"""A line chart drawn with Pillow: one line per series on a white plot with axes and grid."""

from __future__ import annotations

import math

#: Line colours, used in turn.
COLORS = [(214, 39, 40), (44, 160, 44), (31, 119, 180), (23, 190, 207),
          (188, 189, 34), (148, 103, 189), (128, 128, 128)]


def _ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    """Return round tick values covering ``lo`` to ``hi``."""
    span = hi - lo
    if span <= 0 or not math.isfinite(span):
        return [lo]
    raw = span / max(1, count)
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    start = math.ceil(lo / step) * step
    ticks = []
    value = start
    while value <= hi + step * 1e-6 and len(ticks) < 50:
        ticks.append(round(value, 10))
        value += step
    return ticks


def _label(value: float) -> str:
    if abs(value) >= 10000 or (0 < abs(value) < 0.01):
        return f"{value:.2g}"
    return f"{value:g}"


def line_chart(series: list[list[float]], width: int, height: int):
    """Draw each series as a line against its sample index.

    Args:
        series: One list of values per line.
        width: Picture width in pixels.
        height: Picture height in pixels.

    Returns:
        An RGB Pillow image.
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (max(32, width), max(32, height)), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(max(9, min(width, height) // 40))

    values = [v for s in series for v in s if math.isfinite(v)]
    longest = max((len(s) for s in series), default=0)
    lo, hi = (min(values), max(values)) if values else (0.0, 1.0)
    if hi == lo:
        lo, hi = lo - 0.5, hi + 0.5
    pad = (hi - lo) * 0.05
    lo, hi = lo - pad, hi + pad
    x_max = max(1, longest - 1)

    left = int(img.width * 0.12)
    right = img.width - int(img.width * 0.04)
    top = int(img.height * 0.05)
    bottom = img.height - int(img.height * 0.1)

    def to_xy(i: int, v: float) -> tuple[float, float]:
        x = left + (right - left) * (i / x_max)
        y = bottom - (bottom - top) * ((v - lo) / (hi - lo))
        return x, y

    for tick in _ticks(lo, hi):
        _, y = to_xy(0, tick)
        draw.line([(left, y), (right, y)], fill=(225, 225, 225))
        text = _label(tick)
        tw = draw.textlength(text, font=font)
        draw.text((left - tw - 6, y - font.size / 2), text, fill=(60, 60, 60), font=font)
    for tick in _ticks(0, x_max):
        x, _ = to_xy(int(tick) if float(tick).is_integer() else tick, lo)
        draw.line([(x, top), (x, bottom)], fill=(235, 235, 235))
        text = _label(tick)
        tw = draw.textlength(text, font=font)
        draw.text((x - tw / 2, bottom + 4), text, fill=(60, 60, 60), font=font)

    draw.rectangle([left, top, right, bottom], outline=(40, 40, 40))
    for idx, s in enumerate(series):
        points = [to_xy(i, v) for i, v in enumerate(s) if math.isfinite(v)]
        color = COLORS[idx % len(COLORS)]
        if len(points) > 1:
            draw.line(points, fill=color, width=max(1, min(width, height) // 300))
        elif points:
            x, y = points[0]
            draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=color)
    return img
