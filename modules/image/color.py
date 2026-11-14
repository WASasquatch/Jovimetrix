"""Colour helpers: lookup tables, colour matching, dominant colours, harmonies and gradient maps."""

from __future__ import annotations

import math

import torch

from ..enums import EnumCBDeficiency, EnumCBSimulator, EnumColorTheory, EnumInterpolation

from . import PixelType, ImageType, space

from .colormap import apply_lut, colormap

from .convert import image_convert, image_grayscale, image_mask, image_mask_add

from .pixel import pixel_hsv_adjust

from .sample import resize

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def _kmeans(image: ImageType, clusters: int, attempts: int = 3) -> tuple[torch.Tensor, torch.Tensor]:
    """Cluster a frame's RGB colours on 0 to 255; returns ``(centres, labels)``."""
    from .kmeans import kmeans

    pixels = image_convert(image, 3).reshape(-1, 3) * 255.0
    return kmeans(pixels, clusters, iterations=20, epsilon=0.5, attempts=attempts, seed=0)


def _luma(colors: torch.Tensor) -> torch.Tensor:
    return colors[:, 0] * 0.299 + colors[:, 1] * 0.587 + colors[:, 2] * 0.114


def color_image2lut(image: ImageType, num_colors: int = 256) -> torch.Tensor:
    """Build a 256 entry colour table from a frame's dominant colours, dark to light.

    Args:
        image: Source frame.
        num_colors: Colours kept, 1 to 256.

    Returns:
        ``(256, 3)`` table, 0 to 1.
    """
    centers, _ = _kmeans(image, max(1, min(256, int(num_colors))))
    centers = centers[torch.argsort(_luma(centers))]
    index = torch.clamp((torch.arange(256) * len(centers)) // 256, max=len(centers) - 1)
    return centers[index].clamp(0, 255) / 255.0


def color_blind(image: ImageType, deficiency: EnumCBDeficiency,
                simulator: EnumCBSimulator = EnumCBSimulator.AUTOSELECT,
                severity: float = 1.0) -> ImageType:
    """Simulate how a colour deficiency sees a frame.

    Args:
        image: Frame.
        deficiency: Protan, deutan or tritan.
        simulator: Simulation model.
        severity: 0 leaves the frame alone; 1 is full dichromacy.

    Returns:
        The simulated frame, alpha kept.
    """
    from .cvd import simulate

    mask = image_mask(image) if image.shape[2] == 4 else None
    out = simulate(image_convert(image, 3), deficiency, simulator, severity)
    return out if mask is None else image_mask_add(out, mask)


def color_lut_full(dominant_colors: list[tuple[int, int, int]], nodes: int = 33) -> torch.Tensor:
    """Build a 3D LUT sending every RGB node to its nearest dominant colour.

    Args:
        dominant_colors: RGB colours, 0 to 255.
        nodes: Nodes per axis, spread evenly over 0 to 255.

    Returns:
        ``(nodes, nodes, nodes, 3)`` ``uint8`` LUT indexed ``[r, g, b]``, as 2.x gave it.
    """
    palette = torch.tensor(dominant_colors, dtype=torch.float32).reshape(-1, 3)
    axis = torch.linspace(0, 255, int(nodes))
    r, g, b = torch.meshgrid(axis, axis, axis, indexing="ij")
    rgb = torch.stack([r, g, b], dim=-1).reshape(-1, 3)
    index = torch.empty(len(rgb), dtype=torch.long)
    step = 65536
    for start in range(0, len(rgb), step):
        chunk = rgb[start:start + step]
        index[start:start + step] = torch.cdist(chunk, palette).argmin(dim=1)
    lut = palette[index].reshape(int(nodes), int(nodes), int(nodes), 3)
    return lut.round().clamp(0, 255).to(torch.uint8)


def color_lut_match(image: ImageType, colormap_index: int = 2, usermap: ImageType = None,
                    num_colors: int = 255) -> ImageType:
    """Recolour a frame's grey levels through an OpenCV colour map or one built from a picture.

    Args:
        image: Frame.
        colormap_index: ``EnumColorMap`` value, used when ``usermap`` is ``None``.
        usermap: Frame whose dominant colours make the map.
        num_colors: Colours kept from ``usermap``.

    Returns:
        The recoloured frame, alpha kept.
    """
    alpha = image_mask(image) if image.shape[2] == 4 else None
    gray = image_grayscale(image_convert(image, 3))
    lut = color_image2lut(usermap, num_colors) if usermap is not None else colormap(colormap_index)
    out = apply_lut(gray, lut)
    if alpha is not None:
        out = torch.cat([out, alpha.unsqueeze(-1)], dim=2)
    return out


def color_lut_palette(colors: list[tuple[int, int, int]], size: int = 32) -> ImageType:
    """Lay colours side by side as square swatches, ``(size, size * len(colors), 3)``."""
    swatches = torch.tensor(colors, dtype=torch.float32).reshape(-1, 3) / 255.0
    return swatches.repeat_interleave(size, dim=0).unsqueeze(0).expand(size, -1, -1).contiguous()


def color_lut_tonal(colors: list[tuple[int, int, int]], width: int = 256, height: int = 32) -> ImageType:
    """Stack one row per colour, each fading from the colour to black.

    Args:
        colors: RGB colours, 0 to 255.
        width: Width of each row.
        height: Height of each row.

    Returns:
        ``(height * len(colors), width, 3)`` frame.
    """
    if not colors:
        return torch.zeros((height, width, 3))
    ramp = 1.0 - torch.arange(width, dtype=torch.float32) / max(1, width)
    palette = torch.tensor(colors, dtype=torch.float32).reshape(-1, 3)
    rows = torch.floor(palette[:, None, :] * ramp[None, :, None]) / 255.0
    return rows.repeat_interleave(height, dim=0)


def color_lut_visualize(lut: torch.Tensor, size: int = 512) -> ImageType:
    """Show a 3D LUT as a square grid of its blue slices.

    Args:
        lut: ``(n, n, n, 3)`` LUT indexed ``[r, g, b]``, ``uint8`` or 0 to 1.
        size: Side of the result in pixels.

    Returns:
        An RGB frame about ``size`` pixels square.

    Raises:
        ValueError: The LUT is not shaped ``(n, n, n, 3)``.
    """
    if lut.ndim != 4 or lut.shape[3] != 3 or not (lut.shape[0] == lut.shape[1] == lut.shape[2]):
        raise ValueError("A LUT must be shaped (n, n, n, 3), n nodes per axis.")
    if lut.dtype == torch.uint8:
        lut = lut.float() / 255.0
    n = lut.shape[0]
    grid = int(math.ceil(math.sqrt(n)))
    tile = max(1, int(size) // grid)
    img = torch.zeros((tile * grid, tile * grid, 3))
    for b in range(n):
        y = (b // grid) * tile
        x = (b % grid) * tile
        img[y:y + tile, x:x + tile] = resize(lut[:, :, b], tile, tile, EnumInterpolation.NEAREST)
    return img


def color_match_reinhard(image: ImageType, target: ImageType) -> ImageType:
    """Move a frame's colour statistics onto a target's, in Lab.

    Args:
        image: The frame to recolour.
        target: The frame whose colours are matched.

    Returns:
        The recoloured RGB frame.
    """
    lab_tar = space.rgb_to_lab_cv(image_convert(target, 3) * 255.0).clamp(0, 255).reshape(-1, 3).double()
    lab_ori = space.rgb_to_lab_cv(image_convert(image, 3) * 255.0).clamp(0, 255)
    flat = lab_ori.reshape(-1, 3).double()
    mean_tar, std_tar = lab_tar.mean(0), lab_tar.std(0, unbiased=False)
    mean_ori, std_ori = flat.mean(0), flat.std(0, unbiased=False).clamp(min=1e-6)
    ratio = (std_tar / std_ori).to(lab_ori.dtype)
    offset = (mean_tar - mean_ori * std_tar / std_ori).to(lab_ori.dtype)
    lab = (lab_ori * ratio + offset).abs().clamp(0, 255)
    return (space.lab_cv_to_rgb(lab) / 255.0).clamp(0, 1)


def color_mean(image: ImageType) -> list[int]:
    """Mean RGB colour of a frame, ``[r, g, b]`` on 0 to 255."""
    if image.shape[2] == 1:
        return [int(float(image.mean()) * 255.0)] * 3
    return [int(float(image[..., i].mean()) * 255.0) for i in range(3)]


def color_top_used(image: ImageType, top_n: int = 8) -> list[tuple[int, int, int]]:
    """Find a frame's dominant colours with k-means, most used first.

    Args:
        image: Frame.
        top_n: Number of colours.

    Returns:
        RGB colours, 0 to 255.
    """
    centers, labels = _kmeans(image, int(top_n))
    counts = torch.bincount(labels, minlength=len(centers))
    order = torch.sort(counts, descending=True, stable=True).indices
    colors = centers[order].round().clamp(0, 255).long()
    return [tuple(int(v) for v in color) for color in colors.tolist()]

# ==============================================================================
# === COLOR ANALYSIS ===
# ==============================================================================

def _shifted(color: PixelType, *shifts) -> tuple:
    """Rotate a colour's hue by each shift, given as (hue, sat, value, wrap sat, wrap value)."""
    hsv = space.pixel_rgb_to_hsv(color)
    return tuple(space.pixel_hsv_to_rgb(pixel_hsv_adjust(hsv, h, s, v, mod_sat=ms, mod_value=mv))
                 for h, s, v, ms, mv in shifts)


def color_theory(image: ImageType, custom: int = 0,
                 scheme: EnumColorTheory = EnumColorTheory.COMPLIMENTARY) -> tuple[ImageType, ...]:
    """Build a colour harmony from a frame's mean colour.

    Args:
        image: Source frame.
        custom: Separation in degrees for ``CUSTOM_TETRAD``.
        scheme: The harmony.

    Returns:
        Five solid frames the size of ``image``: the mean colour, then up to four harmony
        colours, black where the scheme has fewer.
    """
    color = color_mean(image)
    hue = lambda h: (h, 0, 0, False, False)
    match scheme:
        case EnumColorTheory.MONOCHROMATIC:
            step = 255 / 5
            found = _shifted(color, *[(0, -i * step, -i * step, True, True) for i in range(1, 5)])
        case EnumColorTheory.SPLIT_COMPLIMENTARY:
            found = _shifted(color, hue(75), hue(105))
        case EnumColorTheory.ANALOGOUS:
            found = _shifted(color, hue(30), hue(15), hue(165), hue(150))
        case EnumColorTheory.TRIADIC:
            found = _shifted(color, hue(60), hue(120))
        case EnumColorTheory.SQUARE:
            found = _shifted(color, hue(45), hue(90), hue(135))
        case EnumColorTheory.COMPOUND:
            found = _shifted(color, hue(90), hue(120), hue(150))
        case EnumColorTheory.CUSTOM_TETRAD:
            delta = int(custom) % 90
            found = _shifted(color, hue(-delta), hue(delta), hue(90 - delta), hue(90 + delta))
        case _:
            found = _shifted(color, hue(90))

    colours = [tuple(color)] + list(found) + [(0, 0, 0)] * (4 - len(found))
    h, w = image.shape[:2]
    return tuple(torch.tensor(c, dtype=torch.float32).div(255.0).expand(h, w, 3).contiguous()
                 for c in colours)

# ==============================================================================
# === GRADIENT ===
# ==============================================================================

def image_gradient_expand(image: ImageType) -> ImageType:
    """Turn the top row of a frame, stretched to 256 wide, into a ``(256, 1, 3)`` table."""
    row = resize(image_convert(image, 3), 256, 256)[0]
    return row.reshape(256, 1, 3)


def image_gradient_map(image: ImageType, color_map: ImageType, reverse: bool = False) -> ImageType:
    """Recolour a frame's grey levels through a gradient picture, read left to right.

    Args:
        image: Frame.
        color_map: Gradient picture; its top row is the table.
        reverse: Read the gradient right to left.

    Returns:
        The recoloured RGB frame.
    """
    if reverse:
        color_map = color_map.flip(1)
    table = image_gradient_expand(color_map).reshape(256, 3)
    return apply_lut(image_grayscale(image), table)
