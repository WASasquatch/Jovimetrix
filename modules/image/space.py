"""Colour space conversions on float tensors whose last axis holds the channels.

Functions ending ``_cv`` reproduce OpenCV's 8-bit encodings on a 0 to 255 scale, unrounded, so
arithmetic written against OpenCV's ``uint8`` results carries over: hue in 0 to 180, Lab's L
scaled to 255 with a and b offset by 128, and so on. The others work on 0 to 1.
"""

from __future__ import annotations

import torch

#: sRGB primaries to CIE XYZ, D65, as OpenCV uses them.
RGB2XYZ = ((0.412453, 0.357580, 0.180423),
           (0.212671, 0.715160, 0.072169),
           (0.019334, 0.119193, 0.950227))

#: CIE XYZ to sRGB primaries, D65, as OpenCV uses them.
XYZ2RGB = ((3.240479, -1.53715, -0.498535),
           (-0.969256, 1.875991, 0.041556),
           (0.055648, -0.204043, 1.057311))

#: D65 white point.
WHITE = (0.950456, 1.0, 1.088754)

_LAB_T = 0.008856
_LAB_K = 903.3
_U_N = 4 * WHITE[0] / (WHITE[0] + 15 * WHITE[1] + 3 * WHITE[2])
_V_N = 9 * WHITE[1] / (WHITE[0] + 15 * WHITE[1] + 3 * WHITE[2])

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def apply_matrix(x: torch.Tensor, matrix) -> torch.Tensor:
    """Multiply every colour in ``x`` by a 3 by 3 matrix.

    Args:
        x: Tensor whose last axis holds three channels.
        matrix: Rows of the matrix.

    Returns:
        The transformed colours.
    """
    m = torch.as_tensor(matrix, dtype=x.dtype, device=x.device)
    return x @ m.T


def srgb_to_linear(x: torch.Tensor) -> torch.Tensor:
    """Remove the sRGB transfer curve from values in 0 to 1."""
    return torch.where(x <= 0.04045, x / 12.92, ((x.clamp(min=0) + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x: torch.Tensor) -> torch.Tensor:
    """Apply the sRGB transfer curve, clipping to 0 to 1 first."""
    x = x.clamp(0, 1)
    return torch.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def gray(rgb: torch.Tensor) -> torch.Tensor:
    """Return Rec. 601 luma, keeping a channel axis of one."""
    return rgb[..., 0:1] * 0.299 + rgb[..., 1:2] * 0.587 + rgb[..., 2:3] * 0.114

# ==============================================================================
# === HSV ===
# ==============================================================================

def rgb_to_hsv(rgb: torch.Tensor) -> torch.Tensor:
    """RGB in 0 to 1 to HSV, hue in turns (0 to 1) and saturation and value in 0 to 1."""
    r, g, b = rgb.unbind(-1)
    v = rgb.amax(-1)
    d = v - rgb.amin(-1)
    s = torch.where(v > 0, d / v.clamp(min=1e-12), torch.zeros_like(v))
    safe = d.clamp(min=1e-12)
    h = torch.where(v == r, (g - b) / safe,
                    torch.where(v == g, (b - r) / safe + 2.0, (r - g) / safe + 4.0))
    h = torch.where(d > 0, (h / 6.0).remainder(1.0), torch.zeros_like(h))
    return torch.stack([h, s, v], dim=-1)


def hsv_to_rgb(hsv: torch.Tensor) -> torch.Tensor:
    """HSV, hue in turns, to RGB in 0 to 1."""
    h, s, v = hsv.unbind(-1)
    h6 = h.remainder(1.0) * 6.0
    sector = torch.floor(h6)
    f = h6 - sector
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    index = sector.long().remainder(6).unsqueeze(-1)
    r = torch.stack([v, q, p, p, t, v], dim=-1).gather(-1, index)
    g = torch.stack([t, v, v, q, p, p], dim=-1).gather(-1, index)
    b = torch.stack([p, p, t, v, v, q], dim=-1).gather(-1, index)
    return torch.cat([r, g, b], dim=-1)


def rgb_to_hsv_cv(rgb255: torch.Tensor) -> torch.Tensor:
    """RGB on 0 to 255 to OpenCV's 8-bit HSV: hue 0 to 180, saturation and value 0 to 255."""
    hsv = rgb_to_hsv(rgb255 / 255.0)
    return hsv * torch.tensor((180.0, 255.0, 255.0), dtype=hsv.dtype, device=hsv.device)


def hsv_cv_to_rgb(hsv: torch.Tensor) -> torch.Tensor:
    """OpenCV's 8-bit HSV to RGB on 0 to 255."""
    scale = torch.tensor((180.0, 255.0, 255.0), dtype=hsv.dtype, device=hsv.device)
    return hsv_to_rgb(hsv / scale) * 255.0


def pixel_rgb_to_hsv(color) -> tuple[int, int, int]:
    """One RGB colour, 0 to 255, to OpenCV's rounded 8-bit HSV."""
    rgb = torch.tensor([float(c) for c in tuple(color)[:3]], dtype=torch.float64)
    h, s, v = rgb_to_hsv_cv(rgb).tolist()
    return int(round(h)) % 180, int(round(s)), int(round(v))


def pixel_hsv_to_rgb(hsv) -> tuple[int, int, int]:
    """One 8-bit HSV colour to RGB, 0 to 255; components are truncated to integers first."""
    hsv = torch.tensor([float(int(c)) for c in tuple(hsv)[:3]], dtype=torch.float64)
    return tuple(int(round(min(255.0, max(0.0, c)))) for c in hsv_cv_to_rgb(hsv).tolist())

# ==============================================================================
# === OPENCV 8-BIT SPACES ===
# ==============================================================================

def rgb_to_yuv_cv(rgb255: torch.Tensor) -> torch.Tensor:
    """RGB to OpenCV's YUV, U and V offset by 128."""
    r, g, b = rgb255.unbind(-1)
    y = r * 0.299 + g * 0.587 + b * 0.114
    return torch.stack([y, (b - y) * 0.492 + 128.0, (r - y) * 0.877 + 128.0], dim=-1)


def yuv_cv_to_rgb(yuv: torch.Tensor) -> torch.Tensor:
    """OpenCV's YUV back to RGB on 0 to 255, unclipped."""
    y, u, v = yuv.unbind(-1)
    u = u - 128.0
    v = v - 128.0
    return torch.stack([y + v * 1.140, y - u * 0.395 - v * 0.581, y + u * 2.032], dim=-1)


def rgb_to_xyz_cv(rgb255: torch.Tensor) -> torch.Tensor:
    """RGB to OpenCV's 8-bit XYZ: the matrix applied to the encoded values, without linearising."""
    return apply_matrix(rgb255, RGB2XYZ)


def xyz_cv_to_rgb(xyz: torch.Tensor) -> torch.Tensor:
    """OpenCV's 8-bit XYZ back to RGB on 0 to 255, unclipped."""
    return apply_matrix(xyz, XYZ2RGB)


def _f(t: torch.Tensor) -> torch.Tensor:
    return torch.where(t > _LAB_T, t.clamp(min=0) ** (1 / 3), 7.787 * t + 16.0 / 116.0)


def rgb_to_lab_cv(rgb255: torch.Tensor) -> torch.Tensor:
    """RGB to OpenCV's 8-bit CIE Lab: L scaled to 255, a and b offset by 128."""
    xyz = apply_matrix(srgb_to_linear(rgb255 / 255.0), RGB2XYZ)
    x, y, z = xyz.unbind(-1)
    fx, fy, fz = _f(x / WHITE[0]), _f(y), _f(z / WHITE[2])
    lum = torch.where(y > _LAB_T, 116.0 * fy - 16.0, _LAB_K * y)
    return torch.stack([lum * 2.55, 500.0 * (fx - fy) + 128.0, 200.0 * (fy - fz) + 128.0], dim=-1)


def lab_cv_to_rgb(lab: torch.Tensor) -> torch.Tensor:
    """OpenCV's 8-bit CIE Lab back to RGB on 0 to 255."""
    lum = lab[..., 0] / 2.55
    a = lab[..., 1] - 128.0
    b = lab[..., 2] - 128.0
    low = lum <= _LAB_T * _LAB_K
    y = torch.where(low, lum / _LAB_K, ((lum + 16.0) / 116.0) ** 3)
    fy = torch.where(low, 7.787 * y + 16.0 / 116.0, (lum + 16.0) / 116.0)
    fx = a / 500.0 + fy
    fz = fy - b / 200.0
    edge = 7.787 * _LAB_T + 16.0 / 116.0
    x = torch.where(fx <= edge, (fx - 16.0 / 116.0) / 7.787, fx ** 3) * WHITE[0]
    z = torch.where(fz <= edge, (fz - 16.0 / 116.0) / 7.787, fz ** 3) * WHITE[2]
    rgb = apply_matrix(torch.stack([x, y, z], dim=-1), XYZ2RGB)
    return linear_to_srgb(rgb) * 255.0


def rgb_to_luv_cv(rgb255: torch.Tensor) -> torch.Tensor:
    """RGB to OpenCV's 8-bit CIE Luv: L scaled to 255, u and v moved into 0 to 255."""
    xyz = apply_matrix(srgb_to_linear(rgb255 / 255.0), RGB2XYZ)
    x, y, z = xyz.unbind(-1)
    lum = torch.where(y > _LAB_T, 116.0 * y.clamp(min=0) ** (1 / 3) - 16.0, _LAB_K * y)
    d = 1.0 / (x + 15.0 * y + 3.0 * z).clamp(min=1.1920929e-07)
    u = 13.0 * lum * (4.0 * x * d - _U_N)
    v = 13.0 * lum * (9.0 * y * d - _V_N)
    return torch.stack([lum * 2.55, (u + 134.0) * 255.0 / 354.0, (v + 140.0) * 255.0 / 262.0], dim=-1)


def luv_cv_to_rgb(luv: torch.Tensor) -> torch.Tensor:
    """OpenCV's 8-bit CIE Luv back to RGB on 0 to 255."""
    lum = luv[..., 0] / 2.55
    u = luv[..., 1] * 354.0 / 255.0 - 134.0
    v = luv[..., 2] * 262.0 / 255.0 - 140.0
    y = torch.where(lum <= 8.0, lum / _LAB_K, ((lum + 16.0) / 116.0) ** 3)
    lit = lum > 1e-6
    safe = torch.where(lit, lum, torch.ones_like(lum))
    up = u / (13.0 * safe) + _U_N
    vp = v / (13.0 * safe) + _V_N
    vp = torch.where(vp.abs() < 1e-9, torch.full_like(vp, 1e-9), vp)
    x = torch.where(lit, 2.25 * up * y / vp, torch.zeros_like(y))
    z = torch.where(lit, (12.0 - 3.0 * up - 20.0 * vp) * y * 0.25 / vp, torch.zeros_like(y))
    rgb = apply_matrix(torch.stack([x, torch.where(lit, y, torch.zeros_like(y)), z], dim=-1), XYZ2RGB)
    return linear_to_srgb(rgb) * 255.0
