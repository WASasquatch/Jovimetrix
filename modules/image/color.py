"""Colour helpers: lookup tables, colour matching, dominant colours, harmonies and gradient maps.

Images are RGB or RGBA ``uint8``.
"""

import cv2
import numpy as np

from .. import deps

from ..enums import \
    EnumCBDeficiency, EnumCBSimulator, EnumColorTheory

from . import \
    PixelType, ImageType

from .convert import \
    image_convert, image_grayscale, image_mask, image_mask_add

from .pixel import \
    pixel_hsv_adjust

from .space import \
    rgb_to_hsv, hsv_to_rgb

TYPE_LUT = tuple[int, int, int, int]

#: Simulator class in ``daltonlens.simulate`` for each menu entry.
_SIMULATORS = {
    EnumCBSimulator.AUTOSELECT: "Simulator_AutoSelect",
    EnumCBSimulator.BRETTEL1997: "Simulator_Brettel1997",
    EnumCBSimulator.COBLISV1: "Simulator_CoblisV1",
    EnumCBSimulator.COBLISV2: "Simulator_CoblisV2",
    EnumCBSimulator.MACHADO2009: "Simulator_Machado2009",
    EnumCBSimulator.VIENOT1999: "Simulator_Vienot1999",
    EnumCBSimulator.VISCHECK: "Simulator_Vischeck",
}

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def _kmeans(pixels: np.ndarray, clusters: int, attempts: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Cluster rows of ``pixels`` with OpenCV k-means.

    Args:
        pixels: ``(N, 3)`` samples.
        clusters: Number of clusters, at most ``N``.
        attempts: Restarts; the tightest result is kept.

    Returns:
        ``(centers, labels)``, centres as ``float32`` and one label per sample.
    """
    pixels = np.ascontiguousarray(pixels, dtype=np.float32)
    clusters = int(max(1, min(clusters, len(pixels))))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5)
    cv2.setRNGSeed(0)
    _, labels, centers = cv2.kmeans(pixels, clusters, None, criteria, attempts, cv2.KMEANS_PP_CENTERS)
    return centers, labels.reshape(-1)


def _luma(colors: np.ndarray) -> np.ndarray:
    return colors[:, 0] * 0.299 + colors[:, 1] * 0.587 + colors[:, 2] * 0.114


def color_image2lut(image: ImageType, num_colors: int = 256) -> ImageType:
    """Build a 256 entry colour map from an image's dominant colours, dark to light.

    Args:
        image: Source image.
        num_colors: Colours kept, 1 to 256.

    Returns:
        A ``(256, 1, 3)`` ``uint8`` table for ``cv2.applyColorMap``.
    """
    image = image_convert(image, 3)
    pixels = image.reshape(-1, 3)
    centers, _ = _kmeans(pixels, max(1, min(256, int(num_colors))))
    centers = centers[np.argsort(_luma(centers))]
    index = np.minimum((np.arange(256) * len(centers)) // 256, len(centers) - 1)
    lut = np.clip(centers[index], 0, 255).astype(np.uint8)
    return lut.reshape(256, 1, 3)


def color_blind(image: ImageType, deficiency: EnumCBDeficiency,
                simulator: EnumCBSimulator = EnumCBSimulator.AUTOSELECT,
                severity: float = 1.0) -> ImageType:
    """Simulate how a colour deficiency sees an image.

    Args:
        image: Input image.
        deficiency: Protanopia, deuteranopia or tritanopia.
        simulator: Simulation model.
        severity: 0 = unchanged; 1 = full deficiency.

    Returns:
        The simulated image, alpha kept.
    """
    simulate = deps.require("daltonlens.simulate")
    cc = image.shape[2] if image.ndim == 3 else 1
    mask = image_mask(image) if cc == 4 else None
    image = np.ascontiguousarray(image_convert(image, 3))
    model = getattr(simulate, _SIMULATORS.get(simulator, "Simulator_AutoSelect"))()
    image = model.simulate_cvd(image, simulate.Deficiency[deficiency.value],
                               severity=float(np.clip(severity, 0, 1)))
    if mask is not None:
        image = image_mask_add(image, mask)
    return image


def color_lut_full(dominant_colors: list[tuple[int, int, int]], nodes: int = 33) -> ImageType:
    """Build a 3D LUT mapping every RGB node to its nearest dominant colour.

    Args:
        dominant_colors: RGB colours, 0 to 255.
        nodes: Nodes per axis, spread evenly over 0 to 255.

    Returns:
        A ``(nodes, nodes, nodes, 3)`` ``uint8`` LUT indexed ``[r, g, b]``.
    """
    palette = np.asarray(dominant_colors, dtype=np.float32).reshape(-1, 3)
    axis = np.linspace(0, 255, int(nodes), dtype=np.float32)
    r, g, b = np.meshgrid(axis, axis, axis, indexing="ij")
    rgb = np.stack([r, g, b], axis=-1).reshape(-1, 3)
    indices = np.empty(len(rgb), dtype=np.int64)
    step = 65536
    for start in range(0, len(rgb), step):
        chunk = rgb[start:start + step]
        dist = ((chunk[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
        indices[start:start + step] = dist.argmin(axis=1)
    lut = palette[indices].reshape(int(nodes), int(nodes), int(nodes), 3)
    return np.clip(np.round(lut), 0, 255).astype(np.uint8)


def color_lut_match(image: ImageType, colormap: int = 2,
                    usermap: ImageType = None, num_colors: int = 255) -> ImageType:
    """Recolour an image through an OpenCV colour map or one built from another image.

    Args:
        image: Input image; its grey levels index the map.
        colormap: OpenCV colour map number, used when ``usermap`` is ``None``.
        usermap: Image whose dominant colours make the map.
        num_colors: Colours kept from ``usermap``.

    Returns:
        The recoloured image, alpha kept.
    """
    cc = image.shape[2] if image.ndim == 3 else 1
    alpha = image_mask(image) if cc == 4 else None

    image = image_convert(image, 3)
    if usermap is not None:
        lut = color_image2lut(usermap, num_colors)
        image = cv2.applyColorMap(image, lut)
    else:
        image = cv2.applyColorMap(image, int(colormap))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    if alpha is not None:
        image = image_convert(image, 4)
        image[..., 3] = alpha
    return image


def color_lut_palette(colors: list[tuple[int, int, int]], size: int = 32) -> ImageType:
    """Lay colours side by side as square swatches.

    Args:
        colors: RGB colours.
        size: Side of each swatch in pixels.

    Returns:
        A ``(size, size * len(colors), 3)`` image.
    """
    num_colors = len(colors)
    lut_image = np.zeros((size, size * num_colors, 3), dtype=np.uint8)
    for i, color in enumerate(colors):
        lut_image[:, i * size:(i + 1) * size] = color
    return lut_image


def color_lut_tonal(colors: list[tuple[int, int, int]], width: int = 256, height: int = 32) -> ImageType:
    """Stack one row per colour, each fading from the colour to black.

    Args:
        colors: RGB colours.
        width: Width of each row.
        height: Height of each row.

    Returns:
        A ``(height * len(colors), width, 3)`` image.
    """
    ramp = 1.0 - np.arange(width, dtype=np.float32) / max(1, width)
    rows = []
    for color in colors:
        row = (np.asarray(color, dtype=np.float32)[None, :] * ramp[:, None]).astype(np.uint8)
        rows.append(np.broadcast_to(row[None, :, :], (height, width, 3)))
    if not rows:
        return np.zeros((height, width, 3), dtype=np.uint8)
    return np.ascontiguousarray(np.concatenate(rows, axis=0))


def color_lut_visualize(lut: np.ndarray, size: int = 512) -> ImageType:
    """Show a 3D LUT as a square grid of its blue slices.

    Args:
        lut: ``(n, n, n, 3)`` LUT indexed ``[r, g, b]``.
        size: Side of the result in pixels.

    Returns:
        An RGB image about ``size`` pixels square.

    Raises:
        ValueError: The LUT is not shaped ``(n, n, n, 3)``.
    """
    if lut.ndim != 4 or lut.shape[3] != 3 or not (lut.shape[0] == lut.shape[1] == lut.shape[2]):
        raise ValueError("A LUT must be shaped (n, n, n, 3), n nodes per axis.")

    n = lut.shape[0]
    grid = int(np.ceil(np.sqrt(n)))
    tile = max(1, int(size) // grid)
    img = np.zeros((tile * grid, tile * grid, 3), dtype=np.uint8)
    for b in range(n):
        y = (b // grid) * tile
        x = (b % grid) * tile
        img[y:y + tile, x:x + tile] = cv2.resize(lut[:, :, b], (tile, tile),
                                                 interpolation=cv2.INTER_NEAREST)
    return img


def color_match_reinhard(image: ImageType, target: ImageType) -> ImageType:
    """Move an image's colour statistics onto a target's, in LAB.

    Args:
        image: The image to recolour.
        target: The image whose colours are matched.

    Returns:
        The recoloured RGB image.
    """
    lab_tar = cv2.cvtColor(image_convert(target, 3), cv2.COLOR_RGB2Lab)
    lab_ori = cv2.cvtColor(image_convert(image, 3), cv2.COLOR_RGB2Lab)
    mean_tar, std_tar = cv2.meanStdDev(lab_tar)
    mean_ori, std_ori = cv2.meanStdDev(lab_ori)
    std_ori = np.maximum(std_ori, 1e-6)
    ratio = (std_tar / std_ori).reshape(-1)
    offset = (mean_tar - mean_ori * std_tar / std_ori).reshape(-1)
    lab = cv2.convertScaleAbs(lab_ori * ratio + offset)
    return cv2.cvtColor(lab, cv2.COLOR_Lab2RGB)


def color_mean(image: ImageType) -> list[int]:
    """Return the mean RGB colour of an image.

    Args:
        image: Input image.

    Returns:
        ``[r, g, b]``, 0 to 255.
    """
    cc = image.shape[2] if image.ndim == 3 else 1
    if cc == 1:
        return [int(np.mean(image))] * 3
    return [int(np.mean(image[..., i])) for i in range(3)]


def color_top_used(image: ImageType, top_n: int = 8) -> list[tuple[int, int, int]]:
    """Find an image's dominant colours with k-means, most used first.

    Args:
        image: Input image.
        top_n: Number of colours.

    Returns:
        RGB colours, 0 to 255.
    """
    image = image_convert(image, 3)
    pixels = image.reshape(-1, 3)
    centers, labels = _kmeans(pixels, int(top_n))
    counts = np.bincount(labels, minlength=len(centers))
    order = np.argsort(-counts, kind="stable")
    colors = np.clip(np.round(centers[order]), 0, 255).astype(int)
    return [tuple(int(v) for v in color) for color in colors]

# ==============================================================================
# === COLOR ANALYSIS ===
# ==============================================================================

def color_theory_complementary(color: PixelType) -> PixelType:
    color = rgb_to_hsv(color)
    color_a = pixel_hsv_adjust(color, 90, 0, 0)
    return hsv_to_rgb(color_a)

def color_theory_monochromatic(color: PixelType) -> tuple[PixelType, ...]:
    color = rgb_to_hsv(color)
    sat = 255 / 5
    val = 255 / 5
    color_a = pixel_hsv_adjust(color, 0, -1 * sat, -1 * val, mod_sat=True, mod_value=True)
    color_b = pixel_hsv_adjust(color, 0, -2 * sat, -2 * val, mod_sat=True, mod_value=True)
    color_c = pixel_hsv_adjust(color, 0, -3 * sat, -3 * val, mod_sat=True, mod_value=True)
    color_d = pixel_hsv_adjust(color, 0, -4 * sat, -4 * val, mod_sat=True, mod_value=True)
    return hsv_to_rgb(color_a), hsv_to_rgb(color_b), hsv_to_rgb(color_c), hsv_to_rgb(color_d)

def color_theory_split_complementary(color: PixelType) -> tuple[PixelType, ...]:
    color = rgb_to_hsv(color)
    color_a = pixel_hsv_adjust(color, 75, 0, 0)
    color_b = pixel_hsv_adjust(color, 105, 0, 0)
    return hsv_to_rgb(color_a), hsv_to_rgb(color_b)

def color_theory_analogous(color: PixelType) -> tuple[PixelType, ...]:
    color = rgb_to_hsv(color)
    color_a = pixel_hsv_adjust(color, 30, 0, 0)
    color_b = pixel_hsv_adjust(color, 15, 0, 0)
    color_c = pixel_hsv_adjust(color, 165, 0, 0)
    color_d = pixel_hsv_adjust(color, 150, 0, 0)
    return hsv_to_rgb(color_a), hsv_to_rgb(color_b), hsv_to_rgb(color_c), hsv_to_rgb(color_d)

def color_theory_triadic(color: PixelType) -> tuple[PixelType, ...]:
    color = rgb_to_hsv(color)
    color_a = pixel_hsv_adjust(color, 60, 0, 0)
    color_b = pixel_hsv_adjust(color, 120, 0, 0)
    return hsv_to_rgb(color_a), hsv_to_rgb(color_b)

def color_theory_compound(color: PixelType) -> tuple[PixelType, ...]:
    color = rgb_to_hsv(color)
    color_a = pixel_hsv_adjust(color, 90, 0, 0)
    color_b = pixel_hsv_adjust(color, 120, 0, 0)
    color_c = pixel_hsv_adjust(color, 150, 0, 0)
    return hsv_to_rgb(color_a), hsv_to_rgb(color_b), hsv_to_rgb(color_c)

def color_theory_square(color: PixelType) -> tuple[PixelType, ...]:
    color = rgb_to_hsv(color)
    color_a = pixel_hsv_adjust(color, 45, 0, 0)
    color_b = pixel_hsv_adjust(color, 90, 0, 0)
    color_c = pixel_hsv_adjust(color, 135, 0, 0)
    return hsv_to_rgb(color_a), hsv_to_rgb(color_b), hsv_to_rgb(color_c)

def color_theory_tetrad_custom(color: PixelType, delta:int=0) -> tuple[PixelType, ...]:
    color = rgb_to_hsv(color)
    delta = int(delta) % 90
    color_a = pixel_hsv_adjust(color, -delta, 0, 0)
    color_b = pixel_hsv_adjust(color, delta, 0, 0)
    color_c = pixel_hsv_adjust(color, 90 - delta, 0, 0)
    color_d = pixel_hsv_adjust(color, 90 + delta, 0, 0)
    return hsv_to_rgb(color_a), hsv_to_rgb(color_b), hsv_to_rgb(color_c), hsv_to_rgb(color_d)

def color_theory(image: ImageType, custom: int = 0,
                 scheme: EnumColorTheory = EnumColorTheory.COMPLIMENTARY) -> tuple[ImageType, ...]:
    """Build a colour harmony from an image's mean colour.

    Args:
        image: Source image.
        custom: Separation in degrees for ``CUSTOM_TETRAD``.
        scheme: The harmony.

    Returns:
        Five solid images the size of ``image``: the mean colour, then up to four harmony
        colours, black where the scheme has fewer.
    """
    b = [0, 0, 0]
    c = [0, 0, 0]
    d = [0, 0, 0]
    color = color_mean(image)
    match scheme:
        case EnumColorTheory.MONOCHROMATIC:
            a, b, c, d = color_theory_monochromatic(color)
        case EnumColorTheory.SPLIT_COMPLIMENTARY:
            a, b = color_theory_split_complementary(color)
        case EnumColorTheory.ANALOGOUS:
            a, b, c, d = color_theory_analogous(color)
        case EnumColorTheory.TRIADIC:
            a, b = color_theory_triadic(color)
        case EnumColorTheory.SQUARE:
            a, b, c = color_theory_square(color)
        case EnumColorTheory.COMPOUND:
            a, b, c = color_theory_compound(color)
        case EnumColorTheory.CUSTOM_TETRAD:
            a, b, c, d = color_theory_tetrad_custom(color, custom)
        case _:
            a = color_theory_complementary(color)

    h, w = image.shape[:2]
    return tuple(np.full((h, w, 3), x, dtype=np.uint8) for x in (color, a, b, c, d))

# ==============================================================================
# === GRADIENT ===
# ==============================================================================

def image_gradient_expand(image: ImageType) -> ImageType:
    """Turn the top row of an image into a 256 entry colour table.

    Args:
        image: The gradient image.

    Returns:
        A ``(256, 1, 3)`` ``uint8`` table.
    """
    image = image_convert(image, 3)
    image = cv2.resize(image, (256, 256))
    return image[0, :, :].reshape((256, 1, 3))

def image_gradient_map(image: ImageType, color_map: ImageType, reverse: bool = False) -> ImageType:
    """Recolour an image's grey levels through a gradient image, read left to right.

    Args:
        image: Input image.
        color_map: Gradient image; its top row is the table.
        reverse: Read the gradient right to left.

    Returns:
        The recoloured RGB image.
    """
    if reverse:
        color_map = color_map[:, ::-1]
    gray = image_grayscale(image)
    color_map = image_gradient_expand(np.ascontiguousarray(color_map))
    return cv2.applyColorMap(gray, color_map)
