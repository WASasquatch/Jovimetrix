"""Tonal, colour, edge and pixel adjustments on frames."""

from __future__ import annotations

import torch

from . import ImageType

from ..enums import \
    EnumAdjustBlur, EnumAdjustColor, EnumAdjustEdge, EnumAdjustMorpho, \
    EnumThreshold, EnumThresholdAdapt

from . import kernels, space

from .convert import image_convert, image_mask, image_mask_add

# ==============================================================================
# === LEVELS ===
# ==============================================================================

def _colour_planes(image: ImageType) -> tuple[ImageType, ImageType]:
    """Split a frame into its colour planes and its alpha (``None`` without one)."""
    if image.ndim == 2:
        image = image.unsqueeze(-1)
    if image.shape[2] == 4:
        return image[..., :3], image[..., 3:]
    return image, None


def _rejoin(rgb: ImageType, alpha: ImageType) -> ImageType:
    return rgb if alpha is None else torch.cat([rgb, alpha], dim=2)


def _percentile(values: torch.Tensor, q: float) -> float:
    """``numpy.percentile`` with linear interpolation, for tensors of any size."""
    n = values.numel()
    pos = min(max(q, 0.0), 1.0) * (n - 1)
    lo = int(pos)
    a = float(values.kthvalue(lo + 1).values)
    if lo + 1 >= n or pos == lo:
        return a
    b = float(values.kthvalue(lo + 2).values)
    return a + (pos - lo) * (b - a)


def image_autolevel(image: ImageType, clip_percent: float = 1.0) -> ImageType:
    """Stretch each colour channel between its low and high percentiles; alpha is kept.

    Args:
        image: Frame.
        clip_percent: Percent ignored at each end.

    Returns:
        The stretched frame.
    """
    rgb, alpha = _colour_planes(image)
    out = []
    for c in range(rgb.shape[2]):
        plane = rgb[..., c]
        flat = plane.flatten()
        lo = _percentile(flat, clip_percent / 100.0)
        hi = _percentile(flat, 1.0 - clip_percent / 100.0)
        if hi > lo:
            plane = (plane.clamp(lo, hi) - lo) / (hi - lo)
        out.append(plane)
    return _rejoin(torch.stack(out, dim=2), alpha)


def image_autolevel_histogram(image: ImageType, clip_percent: float = 0.5) -> ImageType:
    """Stretch each colour channel between histogram cut points; alpha is kept.

    Args:
        image: Frame.
        clip_percent: Percent of pixels ignored at each end, 0 to 100.

    Returns:
        The stretched frame.
    """
    rgb, alpha = _colour_planes(image)
    out = []
    for c in range(rgb.shape[2]):
        plane = rgb[..., c]
        levels = (plane.clamp(0, 1) * 255.0)
        hist = torch.histc(levels.float(), bins=256, min=0, max=255)
        cdf = torch.cumsum(hist.double(), 0)
        total = float(cdf[-1])
        lo = int(torch.searchsorted(cdf, torch.tensor([total * clip_percent / 100.0], dtype=torch.float64)))
        hi = int(torch.searchsorted(cdf, torch.tensor([total * (1 - clip_percent / 100.0)], dtype=torch.float64)))
        if hi > lo:
            plane = (levels.clamp(lo, hi) - lo) / (hi - lo)
        out.append(plane)
    return _rejoin(torch.stack(out, dim=2), alpha)

# ==============================================================================
# === FILTERS ===
# ==============================================================================

def image_blur(image: ImageType, op: EnumAdjustBlur = EnumAdjustBlur.BLUR, kernel: int = 1,
               sigmaX: float = 0, sigmaY: float = 0) -> ImageType:
    """Blur every channel.

    Args:
        image: Frame.
        op: Box, stack, Gaussian or median blur.
        kernel: Window size; an even size grows by one.
        sigmaX: Gaussian sigma across; 0 derives it from the size.
        sigmaY: Gaussian sigma down; 0 uses ``sigmaX``.

    Returns:
        The blurred frame.
    """
    if kernel % 2 == 0:
        kernel += 1
    match op:
        case EnumAdjustBlur.STACK_BLUR:
            return kernels.stack_blur(image, kernel)
        case EnumAdjustBlur.GAUSSIAN_BLUR:
            return kernels.gaussian_blur(image, kernel, sigmaX, sigmaY)
        case EnumAdjustBlur.MEDIAN_BLUR:
            return kernels.median_blur(image, kernel)
    return kernels.box_blur(image, kernel, kernel)


def image_edge(image: ImageType, op: EnumAdjustEdge = EnumAdjustEdge.CANNY, kernel: int = 1,
               iterations: int = 1, lo: float = 0, hi: float = 1.) -> ImageType:
    """Find edges.

    Args:
        image: RGB frame.
        op: Edge operator.
        kernel: Aperture or structuring element size; an even size grows by one.
        iterations: Repeats of the OUTLINE gradient.
        lo: CANNY weak threshold, 0 to 1.
        hi: CANNY strong threshold, 0 to 1.

    Returns:
        OUTLINE keeps the channels; the others return one grey channel.
    """
    if kernel % 2 == 0:
        kernel += 1
    gray = space.gray(image[..., :3]) if image.shape[2] >= 3 else image

    match op:
        case EnumAdjustEdge.OUTLINE:
            kernel = max(3, kernel)
            grown = kernels.dilate(image, kernel, kernel, iterations)
            shrunk = kernels.erode(image, kernel, kernel, iterations)
            return (grown - shrunk).clamp(0, 1)

        case EnumAdjustEdge.CANNY:
            blurred = kernels.gaussian_blur(image, kernel, 0.5)
            lo = int(min(255, max(0, lo * 255)))
            hi = int(min(255, max(0, hi * 255)))
            return kernels.canny(blurred * 255.0, lo, hi)

        case EnumAdjustEdge.LAPLACIAN:
            return kernels.laplacian(gray, min(31, kernel)).abs().clamp(0, 1)

        case EnumAdjustEdge.SOBEL:
            kernel = min(31, kernel)
            gx = kernels.sobel(gray, 1, 0, kernel)
            gy = kernels.sobel(gray, 0, 1, kernel)
            return torch.sqrt(gx * gx + gy * gy).clamp(0, 1)

        case EnumAdjustEdge.PREWITT:
            k = float(kernel)
            kx = torch.tensor([[k, 0.0, -k]] * 3)
            # filter2D into uint8 kept only the positive response; that is preserved.
            px = kernels.filter2d(gray, kx).clamp(0, 1)
            py = kernels.filter2d(gray, kx.T.contiguous()).clamp(0, 1)
            return torch.sqrt(px * px + py * py).clamp(0, 1)

        case EnumAdjustEdge.SCHARR:
            gx = kernels.sobel(gray, 1, 0, -1, float(kernel))
            gy = kernels.sobel(gray, 0, 1, -1, float(kernel))
            return torch.sqrt(gx * gx + gy * gy).clamp(0, 1)
    return image


def image_emboss(image: ImageType, azimuth: float = -45.0, elevation: float = 45.0,
                 depth: float = 10.0) -> ImageType:
    """Shade a frame as relief lit from one direction.

    Args:
        image: Frame.
        azimuth: Light direction in degrees; 0 is right, 90 is down.
        elevation: Light height in degrees; 90 is straight down.
        depth: Relief strength.

    Returns:
        The embossed RGB frame.
    """
    import math

    rgb = image_convert(image, 3).double() * 255.0
    gy, gx = torch.gradient(rgb, dim=(0, 1))
    az = math.radians(azimuth - 90)
    el = math.radians(elevation)
    gd = math.cos(el)
    dx, dy, dz = gd * math.cos(az), gd * math.sin(az), math.sin(el)
    gy = gy * depth / 100.0
    gx = gx * depth / 100.0
    length = torch.sqrt(gy * gy + gx * gx + 1.0)
    out = 255.0 * (dx * gy / length + dy * gx / length + dz / length)
    return (out.clamp(0, 255) / 255.0).to(image.dtype)


def image_filter(image: ImageType, start: tuple[int, ...] = (128, 128, 128),
                 end: tuple[int, ...] = (128, 128, 128), fuzz: tuple[float, ...] = (0.5, 0.5, 0.5),
                 use_range: bool = False) -> tuple[ImageType, ImageType]:
    """Keep the pixels whose colour lies in a range.

    Args:
        image: Frame.
        start: Low RGB, 0 to 255.
        end: High RGB, 0 to 255; used when ``use_range`` is on.
        fuzz: Tolerance added either side of the range, per channel, 0 to 1.
        use_range: Use ``start`` to ``end`` rather than ``start`` alone.

    Returns:
        ``(image, mask)``: the frame with everything outside the range black, alpha kept, and
        a ``(H, W)`` mask, 1 inside.
    """
    old_alpha = None
    rgb = image
    if image.shape[2] == 4:
        old_alpha = image[..., 3:]
        rgb = image[..., :3]
    elif image.shape[2] == 1:
        rgb = image.expand(-1, -1, 3)

    fuzz = torch.tensor(fuzz, dtype=rgb.dtype, device=rgb.device)
    low = torch.tensor(start, dtype=rgb.dtype, device=rgb.device) / 255.0
    high = torch.tensor(end, dtype=rgb.dtype, device=rgb.device) / 255.0 if use_range else low.clone()
    low = (low - fuzz).clamp(0, 1)
    high = (high + fuzz).clamp(0, 1)
    mask = ((rgb >= low) & (rgb <= high)).all(dim=2)
    out = torch.where(mask.unsqueeze(-1), rgb, torch.zeros_like(rgb))
    if old_alpha is not None:
        out = torch.cat([out, old_alpha], dim=2)
    return out, mask.to(rgb.dtype)


def image_histogram2(image: ImageType, bins: int = 256) -> ImageType:
    """Draw a frame's grey level histogram, white bars on black, ``bins`` square.

    Args:
        image: Frame.
        bins: Histogram bins and side of the picture.

    Returns:
        The RGB histogram picture.
    """
    gray = space.gray(image[..., :3]) if image.shape[2] >= 3 else image[..., :1]
    levels = (gray.clamp(0, 1) * 255.0).round()
    index = (levels * bins / 256.0).floor().long().clamp(0, bins - 1).flatten()
    hist = torch.bincount(index, minlength=bins).double()
    hist = hist / max(1.0, float(hist.max()))
    heights = (hist * (bins - 1)).long()
    rows = torch.arange(bins, device=heights.device).unsqueeze(1)
    bars = rows >= (bins - 1 - heights).unsqueeze(0)
    return bars.to(image.dtype).unsqueeze(-1).expand(-1, -1, 3).contiguous()


def image_morphology(image: ImageType, op: EnumAdjustMorpho = EnumAdjustMorpho.DILATE,
                     kernel_size: int = 3, iterations: int = 1) -> ImageType:
    """Grow, shrink, open or close shapes with a square structuring element.

    Args:
        image: Frame; every channel is processed.
        op: Operation.
        kernel_size: Side of the square; an even size grows by one.
        iterations: Repeats.

    Returns:
        The processed frame.
    """
    if kernel_size % 2 == 0:
        kernel_size += 1
    k = kernel_size

    def opened(x):
        return kernels.dilate(kernels.erode(x, k, k, iterations), k, k, iterations)

    def closed(x):
        return kernels.erode(kernels.dilate(x, k, k, iterations), k, k, iterations)

    match op:
        case EnumAdjustMorpho.ERODE:
            return kernels.erode(image, k, k, iterations)
        case EnumAdjustMorpho.OPEN:
            return opened(image)
        case EnumAdjustMorpho.CLOSE:
            return closed(image)
        case EnumAdjustMorpho.TOPHAT:
            return (image - opened(image)).clamp(0, 1)
        case EnumAdjustMorpho.BLACKHAT:
            return (closed(image) - image).clamp(0, 1)
    return kernels.dilate(image, k, k, iterations)


def image_sharpen(image: ImageType, amount: float = 0., kernel: int = 3, sigma: float = 0.5,
                  threshold: float = 0) -> ImageType:
    """Unsharp mask.

    Args:
        image: Frame.
        amount: Strength, 0 to 1, scaled by 255 as 2.x did.
        kernel: Blur size; an even size grows by one.
        sigma: Blur sigma.
        threshold: Leave pixels whose difference from the blur is below this, 0 to 1.

    Returns:
        The sharpened frame.
    """
    if kernel and kernel % 2 == 0:
        kernel += 1
    amount = max(0.0, min(255.0, 255.0 * amount))
    blurred = kernels.gaussian_blur(image, kernel, sigma)
    sharp = ((amount + 1) * image - amount * blurred).clamp(0, 1)
    if threshold > 0:
        threshold = max(0.0, min(255.0, 255.0 * threshold)) / 255.0
        sharp = torch.where((image - blurred).abs() < threshold, image, sharp)
    return sharp

# ==============================================================================
# === LIGHT ===
# ==============================================================================

def image_brightness(image: ImageType, brightness: float = 0) -> ImageType:
    """Shift brightness, -1 to 1, by lifting the black point or lowering the white point."""
    brightness = min(1.0, max(-1.0, brightness)) * 255
    shadow, highlight = (brightness, 255) if brightness > 0 else (0, 255 + brightness)
    gain = (highlight - shadow) / 255
    return (image * gain + shadow / 255.0).clamp(0, 1)


def image_contrast(image: ImageType, contrast: float) -> ImageType:
    """Scale contrast, -1 to 1, about the middle of Lab lightness; grey frames directly."""
    contrast = min(1.0, max(-1.0, contrast)) * 255
    factor = (255 * (contrast + 255)) / (255 * (255 - contrast)) if contrast < 255 else 255.0

    if image.shape[2] == 1:
        return ((factor * (image * 255 - 128) + 128) / 255.0).clamp(0, 1)
    rgb, alpha = _colour_planes(image)
    lab = space.rgb_to_lab_cv(rgb * 255.0).clamp(0, 255)
    lab[..., 0] = (factor * (lab[..., 0] - 128) + 128).clamp(0, 255)
    rgb = (space.lab_cv_to_rgb(lab) / 255.0).clamp(0, 1)
    return _rejoin(rgb, alpha)


def image_equalize(image: ImageType) -> ImageType:
    """Equalise the histogram of the luma, keeping the colour; returns RGB."""
    rgb = image_convert(image, 3)
    yuv = space.rgb_to_yuv_cv(rgb * 255.0).clamp(0, 255)
    levels = yuv[..., 0].round().long()
    hist = torch.bincount(levels.flatten(), minlength=256)
    first = int(torch.nonzero(hist)[0])
    total = int(levels.numel())
    if int(hist[first]) == total:
        yuv[..., 0] = float(first)
    else:
        scale = 255.0 / (total - int(hist[first]))
        cdf = torch.cumsum(hist, 0) - hist[first]
        lut = (cdf.double() * scale).round().clamp(0, 255)
        lut[:first + 1] = 0
        yuv[..., 0] = lut.to(yuv.dtype)[levels]
    return (space.yuv_cv_to_rgb(yuv) / 255.0).clamp(0, 1)


def image_exposure(image: ImageType, value: float) -> ImageType:
    """Scale exposure by ``2 ** value`` in linear light."""
    return space.linear_to_srgb(space.srgb_to_linear(image) * (2.0 ** value))


def image_gamma(image: ImageType, gamma: float) -> ImageType:
    """Apply gamma; 0 or less gives black."""
    if gamma <= 0:
        return torch.zeros_like(image)
    return image.clamp(0, 1) ** (1.0 / max(1e-6, gamma))


def image_invert(image: ImageType, value: float) -> ImageType:
    """Blend toward the inverted colour by ``value``, 0 to 1; alpha is kept."""
    value = min(1.0, max(0.0, value))
    rgb, alpha = _colour_planes(image)
    return _rejoin((1 - value) * rgb + value * (1 - rgb), alpha)

# ==============================================================================
# === COLOUR ===
# ==============================================================================

def image_color(image: ImageType, op: EnumAdjustColor = EnumAdjustColor.RGB,
                a: float = 0, b: float = 0, c: float = 0) -> ImageType:
    """Shift three channels of a colour space by -1 to 1 of their 8-bit range.

    The spaces use OpenCV's 8-bit encodings, as 2.x did: hue covers 0 to 180, Lab's L 0 to 255.

    Args:
        image: Frame.
        op: Colour space.
        a: Shift of the first channel.
        b: Shift of the second channel.
        c: Shift of the third channel.

    Returns:
        The shifted frame, alpha kept.
    """
    alpha = image_mask(image) if image.shape[2] == 4 else None
    rgb = image_convert(image, 3) * 255.0
    a, b, c = (min(1.0, max(-1.0, v)) for v in (a, b, c))

    def shift(x, sa, sb, sc):
        delta = torch.tensor((a * sa, b * sb, c * sc), dtype=x.dtype, device=x.device)
        return (x + delta).clamp(0, 255)

    match op:
        case EnumAdjustColor.RGB:
            rgb = shift(rgb, 255, 255, 255)
        case EnumAdjustColor.HSV:
            hsv = space.rgb_to_hsv_cv(rgb)
            h = (hsv[..., 0] + a * 180).remainder(180)
            s = (hsv[..., 1] + b * 255).clamp(0, 255)
            v = (hsv[..., 2] + c * 255).clamp(0, 255)
            rgb = space.hsv_cv_to_rgb(torch.stack([h, s, v], dim=-1))
        case EnumAdjustColor.YUV:
            rgb = space.yuv_cv_to_rgb(shift(space.rgb_to_yuv_cv(rgb).clamp(0, 255), 100, 100, 100))
        case EnumAdjustColor.LAB:
            rgb = space.lab_cv_to_rgb(shift(space.rgb_to_lab_cv(rgb).clamp(0, 255), 255, 127, 127))
        case EnumAdjustColor.LUV:
            rgb = space.luv_cv_to_rgb(shift(space.rgb_to_luv_cv(rgb).clamp(0, 255), 255, 150, 150))
        case EnumAdjustColor.XYZ:
            rgb = space.xyz_cv_to_rgb(shift(space.rgb_to_xyz_cv(rgb).clamp(0, 255), 100, 100, 100))

    rgb = (rgb / 255.0).clamp(0, 1)
    return rgb if alpha is None else image_mask_add(rgb, alpha)

# ==============================================================================
# === PIXEL ===
# ==============================================================================

def image_pixelate(image: ImageType, amount: float) -> ImageType:
    """Replace each block of pixels with its mean.

    Args:
        image: Frame.
        amount: Block size as a fraction of each side, 0 to 1.

    Returns:
        The pixelated frame.
    """
    h, w = image.shape[:2]
    bh = max(1, int(h * amount))
    bw = max(1, int(w * amount))
    if bh == 1 and bw == 1:
        return image.clone()
    rows = torch.minimum(torch.arange(h, device=image.device) // bh, torch.tensor(-(-h // bh) - 1))
    cols = torch.minimum(torch.arange(w, device=image.device) // bw, torch.tensor(-(-w // bw) - 1))
    nh, nw = int(rows.max()) + 1, int(cols.max()) + 1
    cell = (rows.unsqueeze(1) * nw + cols.unsqueeze(0)).flatten()
    flat = image.reshape(h * w, -1).double()
    sums = torch.zeros(nh * nw, flat.shape[1], dtype=flat.dtype, device=flat.device).index_add_(0, cell, flat)
    counts = torch.bincount(cell, minlength=nh * nw).unsqueeze(1).to(flat.dtype)
    means = (sums / counts.clamp(min=1)).to(image.dtype)
    return means[cell].reshape(image.shape)


def image_pixelscale(image: ImageType, amount: float) -> ImageType:
    """Shrink to a square of ``1 - amount`` of the longer side, then enlarge with nearest."""
    from .sample import resize
    from ..enums import EnumInterpolation

    height, width = image.shape[:2]
    amount = min(1, max(0, 1. - amount))
    side = max(1, int(max(width * amount, height * amount, 1)))
    small = resize(image, side, side, EnumInterpolation.LINEAR)
    return resize(small, width, height, EnumInterpolation.NEAREST)


def image_posterize(image: ImageType, amount: float) -> ImageType:
    """Reduce every channel to fewer levels; ``amount`` 0 keeps all 256."""
    levels = min(1, max(0, 1.0 - amount)) * 255
    divisor = 256 / max(1, min(255, levels))
    q = torch.floor(torch.floor(image.clamp(0, 1) * 255.0 + 1e-4) / divisor) * int(divisor)
    return q / 255.0


def image_quantize(image: ImageType, amount: float, iterations: int = 5, epsilon: float = 0.2) -> ImageType:
    """Reduce a frame to ``(1 - amount) * 255`` colours with k-means.

    Args:
        image: Frame.
        amount: 0 keeps 255 colours; 1 keeps one.
        iterations: Most k-means passes.
        epsilon: Stop once no colour moves farther than this, on 0 to 255.

    Returns:
        The quantised frame.
    """
    from .kmeans import kmeans

    levels = int(max(1, min(255, min(1, max(0, 1.0 - amount)) * 255)))
    pixels = (image.reshape(-1, image.shape[2]) * 255.0).float()
    centers, labels = kmeans(pixels, levels, iterations, epsilon)
    centers = centers.clamp(0, 255).round() / 255.0
    return centers[labels].reshape(image.shape).to(image.dtype)


def image_threshold(image: ImageType, threshold: float = 0.5, mode: EnumThreshold = EnumThreshold.BINARY,
                    adapt: EnumThresholdAdapt = EnumThresholdAdapt.ADAPT_NONE, block: int = 3,
                    const: float = 0.) -> ImageType:
    """Threshold each colour channel, or the grey level adaptively.

    Args:
        image: Frame.
        threshold: Level, 0 to 1.
        mode: BINARY, TRUNC or TOZERO.
        adapt: Compare against the local mean or Gaussian mean instead of ``threshold``.
        block: Neighbourhood size for adaptive thresholding.
        const: Subtracted from the local mean, on 0 to 255.

    Returns:
        The thresholded frame, alpha kept.
    """
    import math

    const = max(-100, min(100, const))
    block = max(3, block if block % 2 == 1 else block + 1)
    alpha = image[..., 3:] if image.shape[2] == 4 else None
    rgb = image_convert(image, 3)
    if adapt != EnumThresholdAdapt.ADAPT_NONE:
        gray = (space.gray(rgb) * 255.0).round()
        if adapt == EnumThresholdAdapt.ADAPT_MEAN:
            local = kernels.box_blur(gray, block, block, "replicate")
        else:
            local = kernels.gaussian_blur(gray, block, 0, 0, "replicate")
        keep = gray > (local.round() - math.ceil(const))
        rgb = rgb * keep.to(rgb.dtype)
    else:
        cut = int(threshold * 255)
        level = cut / 255.0
        # Halfway to the next level, so 8-bit inputs compare as whole levels did in 2.x.
        above = rgb > (cut + 0.5) / 255.0
        match mode:
            case EnumThreshold.TRUNC:
                rgb = torch.where(above, torch.full_like(rgb, level), rgb)
            case EnumThreshold.TOZERO:
                rgb = torch.where(above, rgb, torch.zeros_like(rgb))
            case _:
                rgb = above.to(rgb.dtype)
    return _rejoin(rgb, alpha)
