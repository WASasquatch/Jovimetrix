"""Filters on frames: borders, convolution, blurs, morphology, derivatives and edge tracing.

A frame is a float tensor shaped ``(H, W, C)``. Border modes use OpenCV's names, and each
filter keeps the border OpenCV gives it, so results line up with the 2.x pack:

| Mode | Extends ``abcd`` as |
|---|---|
| ``"reflect101"`` | ``dcb|abcd|cba``, OpenCV's default. |
| ``"reflect"`` | ``cba|abcd|dcb`` |
| ``"replicate"`` | ``aaa|abcd|ddd`` |
| ``"wrap"`` | ``bcd|abcd|abc`` |
| ``"constant"`` | a fixed value. |
"""

from __future__ import annotations

from typing import Sequence, Union

import torch
import torch.nn.functional as F

#: Kernels longer than this convolve through the FFT rather than directly.
FFT_FROM = 32

#: Elements one unfolded median chunk may hold.
MEDIAN_CHUNK = 1 << 25

#: OpenCV's fixed kernels for ``getGaussianKernel`` when no sigma is given.
_SMALL_GAUSSIAN = {
    1: (1.0,),
    3: (0.25, 0.5, 0.25),
    5: (0.0625, 0.25, 0.375, 0.25, 0.0625),
    7: (0.03125, 0.109375, 0.21875, 0.28125, 0.21875, 0.109375, 0.03125),
}

Value = Union[float, Sequence[float]]

# ==============================================================================
# === BORDERS ===
# ==============================================================================

def border_index(n: int, before: int, after: int, mode: str, device=None) -> torch.Tensor:
    """Return the source index for each position of an axis grown by a border.

    Args:
        n: Length of the axis.
        before: Positions added before index 0.
        after: Positions added after the last index.
        mode: ``"reflect101"``, ``"reflect"``, ``"replicate"`` or ``"wrap"``.
        device: Device of the result.

    Returns:
        ``n + before + after`` indices into the axis.

    Raises:
        ValueError: ``mode`` is not one of the above.
    """
    i = torch.arange(-before, n + after, device=device)
    if mode == "replicate":
        return i.clamp(0, n - 1)
    if mode == "wrap":
        return i.remainder(n)
    if mode == "reflect101":
        if n == 1:
            return torch.zeros_like(i)
        period = 2 * (n - 1)
        i = i.remainder(period)
        return torch.where(i >= n, period - i, i)
    if mode == "reflect":
        period = 2 * n
        i = i.remainder(period)
        return torch.where(i >= n, period - 1 - i, i)
    raise ValueError(f"Unknown border mode '{mode}'.")


def pad(frame: torch.Tensor, top: int, bottom: int, left: int, right: int,
        mode: str = "reflect101", value: Value = 0.0) -> torch.Tensor:
    """Grow a frame by a border on each side.

    Args:
        frame: ``(H, W, C)`` frame.
        top: Rows added above.
        bottom: Rows added below.
        left: Columns added on the left.
        right: Columns added on the right.
        mode: Border mode; see the module notes.
        value: Fill for ``"constant"``: one number, or one per channel.

    Returns:
        The ``(H + top + bottom, W + left + right, C)`` frame.
    """
    if top == bottom == left == right == 0:
        return frame
    h, w, c = frame.shape
    if mode == "constant":
        fill = torch.as_tensor(value, dtype=frame.dtype, device=frame.device).reshape(-1)
        if fill.numel() == 1:
            out = torch.full((h + top + bottom, w + left + right, c), float(fill[0]),
                             dtype=frame.dtype, device=frame.device)
        else:
            out = fill[:c].repeat(h + top + bottom, w + left + right, 1)
        out[top:top + h, left:left + w] = frame
        return out
    rows = border_index(h, top, bottom, mode, frame.device)
    cols = border_index(w, left, right, mode, frame.device)
    return frame.index_select(0, rows).index_select(1, cols)

# ==============================================================================
# === CONVOLUTION ===
# ==============================================================================

def correlate_axis(x: torch.Tensor, kernel: torch.Tensor, dim: int) -> torch.Tensor:
    """Correlate a tensor with a 1D kernel along one axis, keeping only full windows.

    Args:
        x: Any tensor; the axis must be at least as long as the kernel.
        kernel: 1D weights.
        dim: Axis to filter.

    Returns:
        ``x`` with that axis shortened by ``len(kernel) - 1``.
    """
    kernel = kernel.to(dtype=x.dtype, device=x.device).reshape(-1)
    k = kernel.numel()
    if k == 1:
        return x * kernel[0]
    moved = x.movedim(dim, -1)
    shape = moved.shape
    n = shape[-1]
    flat = moved.reshape(-1, 1, n)
    if k < FFT_FROM:
        out = F.conv1d(flat, kernel.view(1, 1, -1))
    else:
        size = n + k - 1
        spectrum = torch.fft.rfft(flat, size) * torch.fft.rfft(kernel.flip(0), size)
        out = torch.fft.irfft(spectrum, size)[..., k - 1:n]
    return out.reshape(*shape[:-1], n - k + 1).movedim(-1, dim)


def _anchor(k: int) -> tuple[int, int]:
    """Border sizes before and after for a kernel of length ``k``, anchored as OpenCV does."""
    return k // 2, k - 1 - k // 2


def sep_filter(frame: torch.Tensor, kx: torch.Tensor, ky: torch.Tensor,
               border: str = "reflect101", value: Value = 0.0) -> torch.Tensor:
    """Correlate a frame with ``ky`` down its columns and ``kx`` along its rows.

    Args:
        frame: ``(H, W, C)`` frame.
        kx: Horizontal weights.
        ky: Vertical weights.
        border: Border mode.
        value: Fill for a ``"constant"`` border.

    Returns:
        The filtered frame, the same size.
    """
    t, b = _anchor(ky.numel())
    l, r = _anchor(kx.numel())
    x = pad(frame, t, b, l, r, border, value)
    x = correlate_axis(x, ky, 0)
    return correlate_axis(x, kx, 1)


def filter2d(frame: torch.Tensor, kernel: torch.Tensor, border: str = "reflect101") -> torch.Tensor:
    """Correlate every channel with a small 2D kernel, as OpenCV's ``filter2D`` does.

    Args:
        frame: ``(H, W, C)`` frame.
        kernel: ``(kh, kw)`` weights.
        border: Border mode.

    Returns:
        The filtered frame, the same size.
    """
    kernel = kernel.to(dtype=frame.dtype, device=frame.device)
    kh, kw = kernel.shape
    t, b = _anchor(kh)
    l, r = _anchor(kw)
    x = pad(frame, t, b, l, r, border).permute(2, 0, 1).unsqueeze(1)
    return F.conv2d(x, kernel.view(1, 1, kh, kw)).squeeze(1).permute(1, 2, 0)


def box_sum_axis(x: torch.Tensor, k: int, dim: int) -> torch.Tensor:
    """Sum every run of ``k`` values along one axis, in time independent of ``k``.

    Args:
        x: Any tensor.
        k: Run length.
        dim: Axis to sum along.

    Returns:
        ``x`` with that axis shortened by ``k - 1``.
    """
    if k == 1:
        return x
    moved = x.movedim(dim, -1).double()
    total = torch.cumsum(F.pad(moved, (1, 0)), dim=-1)
    return (total[..., k:] - total[..., :-k]).to(x.dtype).movedim(-1, dim)

# ==============================================================================
# === BLURS ===
# ==============================================================================

def box_blur(frame: torch.Tensor, kw: int, kh: int, border: str = "reflect101") -> torch.Tensor:
    """Average every ``kw`` by ``kh`` window, as OpenCV's ``blur`` does.

    Args:
        frame: ``(H, W, C)`` frame.
        kw: Window width.
        kh: Window height.
        border: Border mode.

    Returns:
        The blurred frame.
    """
    t, b = _anchor(kh)
    l, r = _anchor(kw)
    x = pad(frame, t, b, l, r, border)
    x = box_sum_axis(box_sum_axis(x, kh, 0), kw, 1)
    return x / float(kw * kh)


def gaussian_kernel(ksize: int, sigma: float, device=None) -> torch.Tensor:
    """Return OpenCV's ``getGaussianKernel`` weights.

    Args:
        ksize: Odd kernel length.
        sigma: Standard deviation; 0 or less derives it from ``ksize``.
        device: Device of the result.

    Returns:
        ``ksize`` weights summing to 1.
    """
    if sigma <= 0 and ksize in _SMALL_GAUSSIAN:
        return torch.tensor(_SMALL_GAUSSIAN[ksize], dtype=torch.float32, device=device)
    if sigma <= 0:
        sigma = 0.3 * ((ksize - 1) * 0.5 - 1) + 0.8
    x = torch.arange(ksize, dtype=torch.float64, device=device) - (ksize - 1) * 0.5
    k = torch.exp(-(x * x) / (2.0 * sigma * sigma))
    return (k / k.sum()).float()


def gaussian_blur(frame: torch.Tensor, ksize: Union[int, tuple[int, int]] = 0, sigma_x: float = 0.0,
                  sigma_y: float = 0.0, border: str = "reflect101") -> torch.Tensor:
    """Blur with a Gaussian, choosing sizes and sigmas the way OpenCV's ``GaussianBlur`` does.

    Args:
        frame: ``(H, W, C)`` frame.
        ksize: Kernel size, or ``(width, height)``; 0 derives it from the sigma.
        sigma_x: Horizontal sigma; 0 derives it from the size.
        sigma_y: Vertical sigma; 0 uses ``sigma_x``.
        border: Border mode.

    Returns:
        The blurred frame.
    """
    kw, kh = (ksize, ksize) if isinstance(ksize, int) else ksize
    if sigma_y <= 0:
        sigma_y = sigma_x
    if kw <= 0 and sigma_x > 0:
        kw = int(round(sigma_x * 6 + 1)) | 1
    if kh <= 0 and sigma_y > 0:
        kh = int(round(sigma_y * 6 + 1)) | 1
    kw, kh = max(1, kw), max(1, kh)
    kx = gaussian_kernel(kw, sigma_x, frame.device)
    ky = gaussian_kernel(kh, sigma_y, frame.device)
    return sep_filter(frame, kx, ky, border)


def stack_blur(frame: torch.Tensor, ksize: int) -> torch.Tensor:
    """Blur with a tent kernel, which is what OpenCV's ``stackBlur`` computes.

    Args:
        frame: ``(H, W, C)`` frame.
        ksize: Odd kernel size.

    Returns:
        The blurred frame.
    """
    r = ksize // 2
    tent = torch.cat([torch.arange(1, r + 2), torch.arange(r, 0, -1)]).float()
    tent = tent / tent.sum()
    return sep_filter(frame, tent, tent, "replicate")


def median_blur(frame: torch.Tensor, ksize: int) -> torch.Tensor:
    """Take the median of every ``ksize`` square window, on 256 levels, as OpenCV does.

    Small windows sort directly. Larger ones count, level by level, how many values in each
    window fall at or below the level, so the time does not grow with the window.

    Args:
        frame: ``(H, W, C)`` frame, 0 to 1.
        ksize: Odd window size.

    Returns:
        The filtered frame, on 256 levels.
    """
    if ksize <= 1:
        return frame
    r = ksize // 2
    levels = (frame.clamp(0, 1) * 255).round()
    padded = pad(levels, r, r, r, r, "replicate")
    h, w, c = frame.shape
    if ksize <= 7:
        out = []
        step = max(1, MEDIAN_CHUNK // max(1, w * c * ksize * ksize))
        for y in range(0, h, step):
            rows = padded[y:y + min(step, h - y) + 2 * r].permute(2, 0, 1).unsqueeze(1)
            cols = F.unfold(rows, ksize)
            out.append(cols.median(dim=1).values.reshape(c, -1, w).permute(1, 2, 0))
        return torch.cat(out, dim=0) / 255.0

    half = (ksize * ksize) // 2
    lo = int(levels.min().item())
    hi = int(levels.max().item())
    padded = padded.to(torch.uint8)
    result = torch.full(levels.shape, lo, dtype=torch.int32, device=frame.device)
    for v in range(lo, hi):
        count = _window_count((padded <= v).to(torch.int32), ksize)
        result += (count <= half).to(torch.int32)
    return result.to(frame.dtype) / 255.0


def _window_count(flags: torch.Tensor, k: int) -> torch.Tensor:
    """Integer sums of every ``k`` by ``k`` window, keeping only full windows."""
    for dim in (0, 1):
        total = flags.cumsum(dim, dtype=torch.int32)
        n = total.shape[dim]
        sums = total.narrow(dim, k - 1, n - k + 1).clone()
        sums.narrow(dim, 1, n - k).sub_(total.narrow(dim, 0, n - k))
        flags = sums
    return flags

# ==============================================================================
# === MORPHOLOGY ===
# ==============================================================================

def running_max_axis(x: torch.Tensor, k: int, dim: int) -> torch.Tensor:
    """Maximum of every run of ``k`` values along one axis, in time independent of ``k``.

    Args:
        x: Any tensor.
        k: Run length.
        dim: Axis to scan.

    Returns:
        ``x`` with that axis shortened by ``k - 1``.
    """
    if k == 1:
        return x
    moved = x.movedim(dim, -1)
    n = moved.shape[-1]
    count = n - k + 1
    blocks = -(-n // k)
    grown = F.pad(moved, (0, blocks * k - n), value=float("-inf"))
    shaped = grown.reshape(*grown.shape[:-1], blocks, k)
    prefix = shaped.cummax(dim=-1).values.reshape(grown.shape)
    suffix = shaped.flip(-1).cummax(dim=-1).values.flip(-1).reshape(grown.shape)
    out = torch.maximum(suffix[..., :count], prefix[..., k - 1:k - 1 + count])
    return out.movedim(-1, dim)


def dilate(frame: torch.Tensor, kw: int, kh: int, iterations: int = 1) -> torch.Tensor:
    """Grow bright areas with a ``kw`` by ``kh`` rectangle, as OpenCV's ``dilate`` does.

    Args:
        frame: ``(H, W, C)`` frame.
        kw: Rectangle width.
        kh: Rectangle height.
        iterations: Times to repeat.

    Returns:
        The dilated frame.
    """
    for _ in range(max(0, iterations)):
        t, b = _anchor(kh)
        l, r = _anchor(kw)
        x = pad(frame, t, b, l, r, "constant", float("-inf"))
        frame = running_max_axis(running_max_axis(x, kh, 0), kw, 1)
    return frame


def erode(frame: torch.Tensor, kw: int, kh: int, iterations: int = 1) -> torch.Tensor:
    """Shrink bright areas with a ``kw`` by ``kh`` rectangle, as OpenCV's ``erode`` does.

    Args:
        frame: ``(H, W, C)`` frame.
        kw: Rectangle width.
        kh: Rectangle height.
        iterations: Times to repeat.

    Returns:
        The eroded frame.
    """
    return -dilate(-frame, kw, kh, iterations)

# ==============================================================================
# === DERIVATIVES ===
# ==============================================================================

def deriv_kernel(order: int, ksize: int) -> torch.Tensor:
    """Return one axis of OpenCV's Sobel (or, for ``ksize`` -1, Scharr) kernel.

    Args:
        order: Derivative order along this axis.
        ksize: Aperture: 1, 3 to 31, or -1 for Scharr.

    Returns:
        The weights.
    """
    if ksize == -1:
        return torch.tensor((3.0, 10.0, 3.0) if order == 0 else (-1.0, 0.0, 1.0))
    if ksize == 1 and order > 0:
        ksize = 3
    if ksize == 1:
        return torch.tensor((1.0,))
    if ksize == 3:
        return torch.tensor({0: (1.0, 2.0, 1.0), 1: (-1.0, 0.0, 1.0)}.get(order, (1.0, -2.0, 1.0)))
    k = [1] + [0] * ksize
    for _ in range(ksize - order - 1):
        k = [k[0]] + [k[j] + k[j - 1] for j in range(1, ksize + 1)]
    for _ in range(order):
        k = [-k[0]] + [k[j - 1] - k[j] for j in range(1, ksize + 1)]
    return torch.tensor(k[:ksize], dtype=torch.float64)


def sobel(frame: torch.Tensor, dx: int, dy: int, ksize: int = 3, scale: float = 1.0,
          border: str = "reflect101") -> torch.Tensor:
    """OpenCV's ``Sobel`` (or ``Scharr`` with ``ksize`` -1), in floating point.

    Args:
        frame: ``(H, W, C)`` frame.
        dx: Order of the horizontal derivative.
        dy: Order of the vertical derivative.
        ksize: Aperture.
        scale: Factor applied to the result.
        border: Border mode.

    Returns:
        The derivative, the same size.
    """
    # Apertures past 7 have weights in the millions; float32 loses the small differences.
    work = frame.double() if ksize > 7 else frame
    kx = deriv_kernel(dx, ksize).to(work.dtype)
    ky = deriv_kernel(dy, ksize).to(work.dtype)
    return (sep_filter(work, kx, ky, border) * scale).to(frame.dtype)


def laplacian(frame: torch.Tensor, ksize: int = 1, border: str = "reflect101") -> torch.Tensor:
    """OpenCV's ``Laplacian``, in floating point.

    Args:
        frame: ``(H, W, C)`` frame.
        ksize: Aperture; 1 uses the 4-neighbour kernel.
        border: Border mode.

    Returns:
        The second derivative sum, the same size.
    """
    if ksize == 1:
        kernel = torch.tensor([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]])
        return filter2d(frame, kernel, border)
    return sobel(frame, 2, 0, ksize, border=border) + sobel(frame, 0, 2, ksize, border=border)


def canny(frame: torch.Tensor, low: float, high: float) -> torch.Tensor:
    """Trace edges with OpenCV's ``Canny`` rules: 3 by 3 Sobel, L1 magnitude, hysteresis.

    Args:
        frame: ``(H, W, C)`` frame on a 0 to 255 scale; with several channels, each pixel uses
            the channel whose gradient is strongest.
        low: Weak edge threshold.
        high: Strong edge threshold.

    Returns:
        ``(H, W, 1)``: 1 on an edge, 0 elsewhere.
    """
    import numpy as np
    from scipy import ndimage

    if low > high:
        low, high = high, low
    gx = sobel(frame, 1, 0, 3, border="replicate")
    gy = sobel(frame, 0, 1, 3, border="replicate")
    mag = gx.abs() + gy.abs()
    if mag.shape[2] > 1:
        pick = mag.argmax(dim=2, keepdim=True)
        mag = mag.gather(2, pick)
        gx = gx.gather(2, pick)
        gy = gy.gather(2, pick)
    mag, gx, gy = mag[..., 0], gx[..., 0], gy[..., 0]

    m = F.pad(mag, (1, 1, 1, 1))
    left, right = m[1:-1, :-2], m[1:-1, 2:]
    up, down = m[:-2, 1:-1], m[2:, 1:-1]
    ax, ay = gx.abs(), gy.abs()
    tan22 = 0.4142135623730950
    horizontal = ay < ax * tan22
    vertical = ~horizontal & (ay > ax * (tan22 + 2.0))
    differ = (gx < 0) != (gy < 0)
    diag_a = torch.where(differ, m[:-2, 2:], m[:-2, :-2])
    diag_b = torch.where(differ, m[2:, :-2], m[2:, 2:])
    peak = torch.where(horizontal, (mag > left) & (mag >= right),
                       torch.where(vertical, (mag > up) & (mag >= down),
                                   (mag > diag_a) & (mag > diag_b)))
    weak = peak & (mag > low)
    strong = (weak & (mag > high)).cpu().numpy()
    labels, count = ndimage.label(weak.cpu().numpy(), structure=np.ones((3, 3), dtype=bool))
    if count == 0:
        return torch.zeros((*mag.shape, 1), dtype=frame.dtype, device=frame.device)
    keep = np.zeros(count + 1, dtype=bool)
    keep[np.unique(labels[strong])] = True
    keep[0] = False
    edges = torch.from_numpy(keep[labels]).to(device=frame.device, dtype=frame.dtype)
    return edges.unsqueeze(-1)
