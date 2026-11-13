"""Normalisation of a series of numbers to 0 to 1, -1 to 1, standard score or unit length."""

import numpy as np

from ..enums import EnumNormalize


def norm_minmax1(value: np.ndarray) -> np.ndarray:
    span = value.max() - value.min()
    return np.zeros_like(value) if span == 0 else (value - value.min()) / span

def norm_minmax2(value: np.ndarray) -> np.ndarray:
    return 2 * norm_minmax1(value) - 1

def norm_zscore(value: np.ndarray) -> np.ndarray:
    std = value.std()
    return np.zeros_like(value) if std == 0 else (value - value.mean()) / std

def norm_l2(value: np.ndarray) -> np.ndarray:
    length = np.linalg.norm(value)
    return np.zeros_like(value) if length == 0 else value / length


def norm_op(op: EnumNormalize, value: np.ndarray) -> np.ndarray:
    """Normalise a series.

    Args:
        op: The normalisation.
        value: The series.

    Returns:
        The normalised series; a series shorter than two is returned as given.
    """
    value = np.asarray(value, dtype=np.float64)
    if len(value) < 2:
        return value
    if (func := globals().get(f"norm_{op.name.lower()}")) is None:
        raise ValueError(f"'{op.name}' is not a normalisation Jovimetrix knows.")
    return func(value)
