"""Easing curves on normalised time, ``t`` in 0 to 1, as numpy arrays."""

import numpy as np

from ..enums import EnumEase


def ease_linear(t: np.ndarray) -> np.ndarray:
    return t

def ease_quad_in(t: np.ndarray) -> np.ndarray:
    return t * t

def ease_quad_out(t: np.ndarray) -> np.ndarray:
    return -(t * (t - 2))

def ease_quad_in_out(t: np.ndarray) -> np.ndarray:
    return np.where(t < 0.5, 2 * t * t, (-2 * t * t) + (4 * t) - 1)

def ease_cubic_in(t: np.ndarray) -> np.ndarray:
    return t * t * t

def ease_cubic_out(t: np.ndarray) -> np.ndarray:
    return (t - 1) * (t - 1) * (t - 1) + 1

def ease_cubic_in_out(t: np.ndarray) -> np.ndarray:
    return np.where(t < 0.5, 4 * t * t * t,
                    0.5 * (2 * t - 2) * (2 * t - 2) * (2 * t - 2) + 1)

def ease_quartic_in(t: np.ndarray) -> np.ndarray:
    return t * t * t * t

def ease_quartic_out(t: np.ndarray) -> np.ndarray:
    return (t - 1) * (t - 1) * (t - 1) * (1 - t) + 1

def ease_quartic_in_out(t: np.ndarray) -> np.ndarray:
    return np.where(t < 0.5, 8 * t * t * t * t,
                    -8 * (t - 1) * (t - 1) * (t - 1) * (t - 1) + 1)

def ease_quintic_in(t: np.ndarray) -> np.ndarray:
    return t * t * t * t * t

def ease_quintic_out(t: np.ndarray) -> np.ndarray:
    return (t - 1) * (t - 1) * (t - 1) * (t - 1) * (t - 1) + 1

def ease_quintic_in_out(t: np.ndarray) -> np.ndarray:
    return np.where(t < 0.5, 16 * t * t * t * t * t,
                    0.5 * (2 * t - 2) * (2 * t - 2) * (2 * t - 2) * (2 * t - 2) * (2 * t - 2) + 1)

def ease_sin_in(t: np.ndarray) -> np.ndarray:
    return np.sin((t - 1) * np.pi * 0.5) + 1

def ease_sin_out(t: np.ndarray) -> np.ndarray:
    return np.sin(t * np.pi * 0.5)

def ease_sin_in_out(t: np.ndarray) -> np.ndarray:
    return 0.5 * (1 - np.cos(t * np.pi))

def ease_circular_in(t: np.ndarray) -> np.ndarray:
    return 1 - np.sqrt(np.clip(1 - (t * t), 0, None))

def ease_circular_out(t: np.ndarray) -> np.ndarray:
    return np.sqrt(np.clip((2 - t) * t, 0, None))

def ease_circular_in_out(t: np.ndarray) -> np.ndarray:
    return np.where(t < 0.5, 0.5 * (1 - np.sqrt(np.clip(1 - 4 * (t * t), 0, None))),
                    0.5 * (np.sqrt(np.clip(-((2 * t) - 3) * ((2 * t) - 1), 0, None)) + 1))

def ease_exponential_in(t: np.ndarray) -> np.ndarray:
    return np.where(t == 0, 0, np.power(2.0, 10 * (t - 1)))

def ease_exponential_out(t: np.ndarray) -> np.ndarray:
    return np.where(t == 1, 1, 1 - np.power(2.0, -10 * t))

def ease_exponential_in_out(t: np.ndarray) -> np.ndarray:
    return np.where(t == 0, t, np.where(t < 0.5, 0.5 * np.power(2.0, (20 * t) - 10),
                                        -0.5 * np.power(2.0, (-20 * t) + 10) + 1))

def ease_elastic_in(t: np.ndarray) -> np.ndarray:
    return np.sin(13 * np.pi * 0.5 * t) * np.power(2.0, 10 * (t - 1))

def ease_elastic_out(t: np.ndarray) -> np.ndarray:
    return np.sin(-13 * np.pi * 0.5 * (t + 1)) * np.power(2.0, -10 * t) + 1

def ease_elastic_in_out(t: np.ndarray) -> np.ndarray:
    return np.where(t < 0.5, 0.5 * np.sin(13 * np.pi * 0.5 * (2 * t)) * np.power(2.0, 10 * ((2 * t) - 1)),
                    0.5 * (np.sin(-13 * np.pi * 0.5 * ((2 * t - 1) + 1)) * np.power(2.0, -10 * (2 * t - 1)) + 2))

def ease_back_in(t: np.ndarray) -> np.ndarray:
    return t * t * t - t * np.sin(t * np.pi)

def ease_back_out(t: np.ndarray) -> np.ndarray:
    p = 1 - t
    return 1 - (p * p * p - p * np.sin(p * np.pi))

def ease_back_in_out(t: np.ndarray) -> np.ndarray:
    return np.where(t < 0.5, 0.5 * (2 * t) * (2 * t) * (2 * t) - (2 * t) * np.sin((2 * t) * np.pi),
                    0.5 * (1 - (2 * t - 1)) * (1 - (2 * t - 1)) * (1 - (2 * t - 1)) - (1 - (2 * t - 1)) * np.sin((1 - (2 * t - 1)) * np.pi) + 0.5)

def ease_bounce_out(t: np.ndarray) -> np.ndarray:
    return np.where(t < 4 / 11, 121 * t * t / 16,
        np.where(t < 8 / 11, (363 / 40.0 * t * t) - (99 / 10.0 * t) + 17 / 5.0,
        np.where(t < 9 / 10, (4356 / 361.0 * t * t) - (35442 / 1805.0 * t) + 16061 / 1805.0,
                (54 / 5.0 * t * t) - (513 / 25.0 * t) + 268 / 25.0)))

def ease_bounce_in(t: np.ndarray) -> np.ndarray:
    return 1 - ease_bounce_out(1 - t)

def ease_bounce_in_out(t: np.ndarray) -> np.ndarray:
    return np.where(t < 0.5, 0.5 * ease_bounce_in(t * 2), 0.5 * ease_bounce_out(t * 2 - 1) + 0.5)

def ease_none(t: np.ndarray) -> np.ndarray:
    return t


def _curve(op: EnumEase):
    if (func := globals().get(f"ease_{op.name.lower()}")) is None:
        raise ValueError(f"'{op.name}' is not an easing curve Jovimetrix knows.")
    return func


def ease_op(op: EnumEase, values: np.ndarray, steps: int,
            clip: tuple[float, float] = (0, 1), duration: float = 1.0) -> np.ndarray:
    """Resample ``values`` along an easing curve.

    Args:
        op: Easing curve.
        values: The values to ease through.
        steps: Number of output samples.
        clip: Range of the curve's time axis used.
        duration: Normalised duration, 0 to 1.

    Returns:
        ``steps`` values interpolated from ``values``.
    """
    func = _curve(op)
    values = np.asarray(values, dtype=np.float64)
    alpha = np.linspace(0, 1, steps)
    t = clip[0] * (1 - alpha) + clip[1] * alpha
    t = t / max(min(duration, 1), 1e-8)

    eased = np.asarray(func(t), dtype=np.float64)
    indices = eased * (len(values) - 1)
    lower = np.clip(np.floor(indices).astype(int), 0, len(values) - 1)
    upper = np.clip(np.ceil(indices).astype(int), 0, len(values) - 1)
    frac = indices - np.floor(indices)
    return values[lower] * (1 - frac) + values[upper] * frac
