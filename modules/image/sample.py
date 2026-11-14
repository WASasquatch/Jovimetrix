"""Resampling frames: resizing with OpenCV's interpolations, remapping and warping.

A frame is a float tensor shaped ``(H, W, C)``. Coordinates follow OpenCV: pixel ``(0, 0)`` is
centred on ``(0.0, 0.0)``.
"""

from __future__ import annotations

import math
from typing import Sequence, Union

import torch

from ..enums import EnumInterpolation

Value = Union[float, Sequence[float]]

# ==============================================================================
# === RESIZE ===
# ==============================================================================

def _taps_nearest(n_in: int, n_out: int, exact: bool, scale: float) -> tuple[torch.Tensor, torch.Tensor]:
    if exact:
        # OpenCV's INTER_NEAREST_EXACT: pixel centres in 16-bit fixed point.
        step = ((n_in << 16) + n_out // 2) // n_out
        start = step // 2 - n_in % 2
        src = (torch.arange(n_out, dtype=torch.int64) * step + start) >> 16
    else:
        src = torch.floor(torch.arange(n_out, dtype=torch.float64) * scale).long()
    return src.clamp(0, n_in - 1).unsqueeze(0), torch.ones(1, n_out, dtype=torch.float64)


def _taps_window(n_in: int, n_out: int, offsets: range, weight, scale: float) -> tuple[torch.Tensor, torch.Tensor]:
    src = (torch.arange(n_out, dtype=torch.float64) + 0.5) * scale - 0.5
    base = torch.floor(src)
    frac = src - base
    index = torch.stack([(base + o).clamp(0, n_in - 1).long() for o in offsets])
    return index, weight(frac)


def _cubic(frac: torch.Tensor) -> torch.Tensor:
    a = -0.75
    x = frac
    w0 = ((a * (x + 1) - 5 * a) * (x + 1) + 8 * a) * (x + 1) - 4 * a
    w1 = ((a + 2) * x - (a + 3)) * x * x + 1
    w2 = ((a + 2) * (1 - x) - (a + 3)) * (1 - x) * (1 - x) + 1
    return torch.stack([w0, w1, w2, 1 - w0 - w1 - w2])


def _lanczos4(frac: torch.Tensor) -> torch.Tensor:
    d = torch.stack([frac + 3 - i for i in range(8)])
    pd = math.pi * d
    w = torch.where(d.abs() < 1e-9, torch.ones_like(d),
                    torch.sin(pd) * torch.sin(pd / 4) / (pd * pd / 4).clamp(min=1e-18))
    return w / w.sum(dim=0, keepdim=True)


def _taps_area(n_in: int, n_out: int, scale: float) -> tuple[torch.Tensor, torch.Tensor]:
    """Coverage weights for shrinking, as OpenCV's ``INTER_AREA`` computes them."""
    rows = []
    for dx in range(n_out):
        f1 = dx * scale
        f2 = f1 + scale
        s1 = math.ceil(f1)
        s2 = math.floor(f2)
        cell = min(scale, n_in - f1)
        taps = []
        if s1 - f1 > 1e-3:
            taps.append((s1 - 1, (s1 - f1) / cell))
        taps.extend((sx, 1.0 / cell) for sx in range(s1, min(s2, n_in)))
        if f2 - s2 > 1e-3 and s2 < n_in:
            taps.append((s2, min(min(f2 - s2, 1.0), cell) / cell))
        rows.append(taps)
    width = max(len(t) for t in rows)
    index = torch.zeros(width, n_out, dtype=torch.long)
    weight = torch.zeros(width, n_out, dtype=torch.float64)
    for dx, taps in enumerate(rows):
        for t, (sx, w) in enumerate(taps):
            index[t, dx] = min(max(sx, 0), n_in - 1)
            weight[t, dx] = w
    return index, weight


def _taps_area_up(n_in: int, n_out: int, scale: float) -> tuple[torch.Tensor, torch.Tensor]:
    """OpenCV's ``INTER_AREA`` weights when it does not shrink: linear with snapped fractions."""
    inv = 1.0 / scale
    dx = torch.arange(n_out, dtype=torch.float64)
    sx = torch.floor(dx * scale)
    fx = (dx + 1) - (sx + 1) * inv
    fx = torch.where(fx <= 0, torch.zeros_like(fx), fx - torch.floor(fx))
    fx = torch.where((sx < 0) | (sx >= n_in - 1), torch.zeros_like(fx), fx)
    sx = sx.clamp(0, n_in - 1)
    index = torch.stack([sx, (sx + 1).clamp(max=n_in - 1)]).long()
    return index, torch.stack([1 - fx, fx])


def _taps(n_in: int, n_out: int, sample: EnumInterpolation, shrink_both: bool, scale: float):
    if sample == EnumInterpolation.NEAREST:
        return _taps_nearest(n_in, n_out, False, scale)
    if sample == EnumInterpolation.NEAREST_EXACT:
        return _taps_nearest(n_in, n_out, True, scale)
    if sample == EnumInterpolation.CUBIC:
        return _taps_window(n_in, n_out, range(-1, 3), _cubic, scale)
    if sample == EnumInterpolation.LANCZOS4:
        return _taps_window(n_in, n_out, range(-3, 5), _lanczos4, scale)
    if sample == EnumInterpolation.AREA:
        return _taps_area(n_in, n_out, scale) if shrink_both else _taps_area_up(n_in, n_out, scale)
    return _taps_window(n_in, n_out, range(0, 2), lambda f: torch.stack([1 - f, f]), scale)


def _apply(x: torch.Tensor, index: torch.Tensor, weight: torch.Tensor, dim: int) -> torch.Tensor:
    moved = x.movedim(dim, 0)
    index = index.to(moved.device)
    weight = weight.to(dtype=moved.dtype, device=moved.device)
    view = (-1,) + (1,) * (moved.ndim - 1)
    out = moved.index_select(0, index[0]) * weight[0].view(view)
    for t in range(1, index.shape[0]):
        out = out + moved.index_select(0, index[t]) * weight[t].view(view)
    return out.movedim(0, dim)


def resize(frame: torch.Tensor, width: int, height: int,
           sample: EnumInterpolation = EnumInterpolation.LINEAR, factor: float = 0.0) -> torch.Tensor:
    """Resize a frame with one of OpenCV's interpolations.

    Args:
        frame: ``(H, W, C)`` frame.
        width: New width, at least 1.
        height: New height, at least 1.
        sample: Interpolation.
        factor: When above 0, sample at exactly this scale, as ``cv2.resize`` does when given
            ``fx`` and ``fy``, rather than at the ratio of the rounded sizes.

    Returns:
        The resized frame, clipped to 0 to 1 when the interpolation can overshoot.
    """
    h, w = frame.shape[:2]
    width, height = max(1, int(width)), max(1, int(height))
    if (w, h) == (width, height):
        return frame.clone()
    shrink_both = (w >= width and h >= height) if factor <= 0 else factor <= 1
    out = frame
    if width != w:
        scale_x = 1.0 / factor if factor > 0 else w / width
        out = _apply(out, *_taps(w, width, sample, shrink_both, scale_x), dim=1)
    if height != h:
        scale_y = 1.0 / factor if factor > 0 else h / height
        out = _apply(out, *_taps(h, height, sample, shrink_both, scale_y), dim=0)
    if sample in (EnumInterpolation.CUBIC, EnumInterpolation.LANCZOS4):
        out = out.clamp(0, 1)
    return out

# ==============================================================================
# === REMAP AND WARP ===
# ==============================================================================

def _gather(frame: torch.Tensor, xi: torch.Tensor, yi: torch.Tensor, border: str,
            fill: torch.Tensor) -> torch.Tensor:
    h, w, c = frame.shape
    if border == "wrap":
        return frame[yi.remainder(h), xi.remainder(w)]
    if border == "replicate":
        return frame[yi.clamp(0, h - 1), xi.clamp(0, w - 1)]
    inside = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
    picked = frame[yi.clamp(0, h - 1), xi.clamp(0, w - 1)]
    return torch.where(inside.unsqueeze(-1), picked, fill)


def remap(frame: torch.Tensor, map_x: torch.Tensor, map_y: torch.Tensor, nearest: bool = False,
          border: str = "constant", value: Value = 0.0) -> torch.Tensor:
    """Sample a frame at given coordinates, as OpenCV's ``remap`` does.

    Args:
        frame: ``(H, W, C)`` source.
        map_x: Source x for every output pixel.
        map_y: Source y for every output pixel.
        nearest: Nearest-neighbour rather than bilinear sampling.
        border: ``"constant"``, ``"replicate"`` or ``"wrap"``.
        value: Fill outside the source for ``"constant"``: one number, or one per channel.

    Returns:
        The sampled frame, shaped like the maps plus the channels.
    """
    c = frame.shape[2]
    fill = torch.as_tensor(value, dtype=frame.dtype, device=frame.device).reshape(-1)
    fill = fill.expand(c) if fill.numel() == 1 else fill[:c]
    map_x = map_x.to(device=frame.device, dtype=torch.float64)
    map_y = map_y.to(device=frame.device, dtype=torch.float64)
    if nearest:
        return _gather(frame, torch.round(map_x).long(), torch.round(map_y).long(), border, fill)
    x0 = torch.floor(map_x)
    y0 = torch.floor(map_y)
    fx = (map_x - x0).to(frame.dtype).unsqueeze(-1)
    fy = (map_y - y0).to(frame.dtype).unsqueeze(-1)
    x0 = x0.long()
    y0 = y0.long()
    top = _gather(frame, x0, y0, border, fill) * (1 - fx) + _gather(frame, x0 + 1, y0, border, fill) * fx
    bottom = _gather(frame, x0, y0 + 1, border, fill) * (1 - fx) + \
        _gather(frame, x0 + 1, y0 + 1, border, fill) * fx
    return top * (1 - fy) + bottom * fy


def _grid(width: int, height: int, device) -> tuple[torch.Tensor, torch.Tensor]:
    ys, xs = torch.meshgrid(torch.arange(height, dtype=torch.float64, device=device),
                            torch.arange(width, dtype=torch.float64, device=device), indexing="ij")
    return xs, ys


def warp_affine(frame: torch.Tensor, matrix, width: int, height: int, border: str = "constant",
                value: Value = 0.0) -> torch.Tensor:
    """Warp with a 2 by 3 forward matrix, bilinear, as OpenCV's ``warpAffine`` does.

    Args:
        frame: ``(H, W, C)`` source.
        matrix: Source to output mapping.
        width: Output width.
        height: Output height.
        border: ``"constant"``, ``"replicate"`` or ``"wrap"``.
        value: Fill for ``"constant"``.

    Returns:
        The warped frame.
    """
    m = torch.as_tensor(matrix, dtype=torch.float64).reshape(2, 3)
    full = torch.cat([m, torch.tensor([[0.0, 0.0, 1.0]], dtype=torch.float64)])
    inv = torch.linalg.inv(full)
    xs, ys = _grid(width, height, frame.device)
    inv = inv.to(frame.device)
    sx = inv[0, 0] * xs + inv[0, 1] * ys + inv[0, 2]
    sy = inv[1, 0] * xs + inv[1, 1] * ys + inv[1, 2]
    return remap(frame, sx, sy, border=border, value=value)


def warp_perspective(frame: torch.Tensor, matrix, width: int, height: int) -> torch.Tensor:
    """Warp with a 3 by 3 forward homography, bilinear, black outside, as OpenCV does.

    Args:
        frame: ``(H, W, C)`` source.
        matrix: Source to output homography.
        width: Output width.
        height: Output height.

    Returns:
        The warped frame.
    """
    inv = torch.linalg.inv(torch.as_tensor(matrix, dtype=torch.float64).reshape(3, 3)).to(frame.device)
    xs, ys = _grid(width, height, frame.device)
    w = inv[2, 0] * xs + inv[2, 1] * ys + inv[2, 2]
    w = torch.where(w.abs() < 1e-12, torch.full_like(w, 1e-12), w)
    sx = (inv[0, 0] * xs + inv[0, 1] * ys + inv[0, 2]) / w
    sy = (inv[1, 0] * xs + inv[1, 1] * ys + inv[1, 2]) / w
    return remap(frame, sx, sy)


def rotation_matrix(center: tuple[float, float], angle: float, scale: float = 1.0) -> list[list[float]]:
    """OpenCV's ``getRotationMatrix2D``: degrees, counter-clockwise on screen.

    Args:
        center: Pivot ``(x, y)`` in pixels.
        angle: Degrees.
        scale: Uniform scale.

    Returns:
        The 2 by 3 matrix.
    """
    a = math.radians(angle)
    alpha = scale * math.cos(a)
    beta = scale * math.sin(a)
    cx, cy = center
    return [[alpha, beta, (1 - alpha) * cx - beta * cy],
            [-beta, alpha, beta * cx + (1 - alpha) * cy]]


def perspective_matrix(src: Sequence[tuple[float, float]],
                       dst: Sequence[tuple[float, float]]) -> list[list[float]]:
    """OpenCV's ``getPerspectiveTransform``: the homography taking four points onto four others.

    Args:
        src: Four ``(x, y)`` points.
        dst: Where each lands.

    Returns:
        The 3 by 3 matrix.
    """
    a = []
    b = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -x * u, -y * u])
        b.append(u)
        a.append([0, 0, 0, x, y, 1, -x * v, -y * v])
        b.append(v)
    h = torch.linalg.solve(torch.tensor(a, dtype=torch.float64), torch.tensor(b, dtype=torch.float64))
    return torch.cat([h, torch.ones(1, dtype=torch.float64)]).reshape(3, 3).tolist()


def polar_inverse(frame: torch.Tensor, center: tuple[float, float], radius: float) -> torch.Tensor:
    """Wrap a frame whose columns are radius and rows are angle into a disc, as OpenCV's
    ``linearPolar`` does with ``WARP_INVERSE_MAP``; nearest sampling, black outside.

    Args:
        frame: ``(H, W, C)`` polar frame.
        center: Disc centre in output pixels.
        radius: Radius the last column reaches.

    Returns:
        The frame, the same size.
    """
    h, w, _ = frame.shape
    xs, ys = _grid(w, h, frame.device)
    dx = xs - center[0]
    dy = ys - center[1]
    rho = torch.sqrt(dx * dx + dy * dy) * (w / max(radius, 1e-9))
    phi = torch.atan2(dy, dx).remainder(2 * math.pi) * (h / (2 * math.pi))
    xi = torch.round(rho).long()
    yi = torch.round(phi).long().remainder(h)
    inside = (xi >= 0) & (xi < w)
    picked = frame[yi, xi.clamp(0, w - 1)]
    return torch.where(inside.unsqueeze(-1), picked, torch.zeros_like(picked))
