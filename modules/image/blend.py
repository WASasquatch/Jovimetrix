"""Layer blending: thirty blend and composite modes on RGBA frames.

The formulas and the alpha compositing follow the ``blendmodes`` package (MIT, FredHappyface,
after Paint.NET, the OpenRaster spec and pashango's work), which Jovimetrix 2.x called. That
package mapped ADDITIVE and GLOW to plain NORMAL; here both do what their names say.
"""

from __future__ import annotations

import torch

from ..enums import EnumBlendType

# ==============================================================================
# === SEPARABLE AND NON-SEPARABLE MODES ===
# ==============================================================================

def _safe_div(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    return a / torch.where(b == 0, torch.ones_like(b), b)


def _lum(c: torch.Tensor) -> torch.Tensor:
    return c[..., 0] * 0.299 + c[..., 1] * 0.587 + c[..., 2] * 0.114


def _set_lum(c: torch.Tensor, lum: torch.Tensor) -> torch.Tensor:
    c = c + (lum - _lum(c)).unsqueeze(-1)
    l = _lum(c).unsqueeze(-1)
    lo = c.amin(-1, keepdim=True)
    hi = c.amax(-1, keepdim=True)
    c = torch.where(lo < 0, l + _safe_div((c - l) * l, l - lo), c)
    return torch.where(hi > 1, l + _safe_div((c - l) * (1 - l), hi - l), c)


def _sat(c: torch.Tensor) -> torch.Tensor:
    return c.amax(-1) - c.amin(-1)


def _set_sat(c: torch.Tensor, sat: torch.Tensor) -> torch.Tensor:
    ordered, order = c.sort(dim=-1)
    lo, mid, hi = ordered.unbind(-1)
    span = hi - lo
    live = span > 0
    mid = torch.where(live, _safe_div((mid - lo) * sat, span), torch.zeros_like(mid))
    hi = torch.where(live, sat, torch.zeros_like(hi))
    values = torch.stack([torch.zeros_like(lo), mid, hi], dim=-1)
    return torch.empty_like(c).scatter_(-1, order, values)


def _burn(b: torch.Tensor, f: torch.Tensor) -> torch.Tensor:
    return torch.where(f != 0, (1 - _safe_div(1 - b, f)).clamp(min=0), torch.zeros_like(b))


def _dodge(b: torch.Tensor, f: torch.Tensor) -> torch.Tensor:
    return torch.where(f != 1, _safe_div(b, 1 - f).clamp(max=1), torch.ones_like(b))


def _to_int(x: torch.Tensor) -> torch.Tensor:
    return (x * 255).round().clamp(0, 255).to(torch.uint8)


_MODES = {
    EnumBlendType.NORMAL: lambda b, f: f,
    EnumBlendType.ADDITIVE: lambda b, f: (b + f).clamp(max=1),
    EnumBlendType.MULTIPLY: lambda b, f: (f * b).clamp(0, 1),
    EnumBlendType.BURN: _burn,
    EnumBlendType.DODGE: _dodge,
    EnumBlendType.REFLECT: lambda b, f: torch.where(f != 1, _safe_div(b * b, 1 - f).clamp(max=1),
                                                    torch.ones_like(b)),
    EnumBlendType.GLOW: lambda b, f: torch.where(b != 1, _safe_div(f * f, 1 - b).clamp(max=1),
                                                 torch.ones_like(b)),
    EnumBlendType.OVERLAY: lambda b, f: torch.where(b < 0.5, 2 * b * f, 1 - 2 * (1 - b) * (1 - f)),
    EnumBlendType.DIFFERENCE: lambda b, f: (b - f).abs(),
    EnumBlendType.NEGATION: lambda b, f: (b - f).clamp(min=0),
    EnumBlendType.LIGHTEN: torch.maximum,
    EnumBlendType.DARKEN: torch.minimum,
    EnumBlendType.SCREEN: lambda b, f: b + f - b * f,
    EnumBlendType.XOR: lambda b, f: (_to_int(b) ^ _to_int(f)).to(b.dtype) / 255.0,
    EnumBlendType.SOFT: lambda b, f: (1 - b) * b * f + b * (1 - (1 - b) * (1 - f)),
    EnumBlendType.HARD: lambda b, f: torch.where(f < 0.5, (b * 2 * f).clamp(max=1),
                                                 (1 - (1 - b) * (1 - (f - 0.5) * 2)).clamp(max=1)),
    EnumBlendType.EXTRACT: lambda b, f: (b - f + 0.5).clamp(0, 1),
    EnumBlendType.MERGE: lambda b, f: (b + f - 0.5).clamp(0, 1),
    EnumBlendType.DIVIDE: lambda b, f: ((256.0 / 255.0 * b) / (1.0 / 255.0 + f)).clamp(max=1),
    EnumBlendType.PIN: lambda b, f: torch.where(f < 0.5, torch.minimum(b, 2 * f),
                                                torch.maximum(b, 2 * (f - 0.5))),
    EnumBlendType.VIVID: lambda b, f: torch.where(f < 0.5, _burn(b, f * 2), _dodge(b, 2 * (f - 0.5))),
    EnumBlendType.EXCLUSION: lambda b, f: b + f - 2 * b * f,
    EnumBlendType.HUE: lambda b, f: _set_lum(_set_sat(f, _sat(b)), _lum(b)),
    EnumBlendType.SATURATION: lambda b, f: _set_lum(_set_sat(b, _sat(f)), _lum(b)),
    EnumBlendType.COLOR: lambda b, f: _set_lum(f, _lum(b)),
    EnumBlendType.LUMINOSITY: lambda b, f: _set_lum(b, _lum(f)),
}

# ==============================================================================
# === COMPOSITING ===
# ==============================================================================

def _composite(mode: EnumBlendType, ab: torch.Tensor, af: torch.Tensor, cb: torch.Tensor,
               cf: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Porter-Duff operators for the four modes that only move alpha."""
    if mode == EnumBlendType.DESTIN:
        out = ab * af
        return _safe_div((ab * af).unsqueeze(-1) * cb, out.unsqueeze(-1)), out
    if mode == EnumBlendType.DESTOUT:
        out = ab * (1 - af)
        return _safe_div((ab * (1 - af)).unsqueeze(-1) * cb, out.unsqueeze(-1)), out
    if mode == EnumBlendType.DESTATOP:
        out = af * (1 - ab) + ab * af
        rgb = (af * (1 - ab)).unsqueeze(-1) * cf + (ab * af).unsqueeze(-1) * cb
        return _safe_div(rgb, out.unsqueeze(-1)), out
    out = af * ab + ab * (1 - af)
    rgb = (af * ab).unsqueeze(-1) * cf + (ab * (1 - af)).unsqueeze(-1) * cb
    return _safe_div(rgb, out.unsqueeze(-1)), out


def blend_layers(background: torch.Tensor, foreground: torch.Tensor, mode: EnumBlendType,
                 opacity: float = 1.0) -> torch.Tensor:
    """Blend an RGBA foreground over an RGBA background of the same size.

    Args:
        background: ``(H, W, 4)`` frame, 0 to 1.
        foreground: ``(H, W, 4)`` frame, 0 to 1.
        mode: Blend or composite mode.
        opacity: Foreground opacity, 0 to 1.

    Returns:
        The ``(H, W, 4)`` result, 0 to 1.
    """
    cb, ab = background[..., :3], background[..., 3]
    cf, af = foreground[..., :3], foreground[..., 3] * float(opacity)
    if mode in (EnumBlendType.DESTIN, EnumBlendType.DESTOUT, EnumBlendType.SRCATOP,
                EnumBlendType.DESTATOP):
        rgb, alpha = _composite(mode, ab, af, cb, cf)
    else:
        alpha = af + ab - af * ab
        mixed = _MODES.get(mode, _MODES[EnumBlendType.NORMAL])(cb, cf)
        rgb = ((1 - af) * ab).unsqueeze(-1) * cb + ((1 - ab) * af).unsqueeze(-1) * cf + \
            (ab * af).unsqueeze(-1) * mixed
        rgb = _safe_div(rgb, alpha.unsqueeze(-1))
    out = torch.cat([rgb, alpha.unsqueeze(-1)], dim=-1)
    return torch.nan_to_num(out, nan=0.0, posinf=1.0, neginf=0.0).clamp(0, 1)
