"""Small vector helpers built on NumPy."""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np


def vec3(values: Any, default: Iterable[float] = (0.0, 0.0, 0.0)) -> np.ndarray:
    """Return a three-element float vector."""

    arr = np.array(values if values is not None else list(default), dtype=float)
    if arr.shape != (3,):
        raise ValueError(f"expected a 3-vector, got shape {arr.shape}")
    return arr


def norm(values: np.ndarray) -> float:
    return float(np.linalg.norm(values))


def unit(values: np.ndarray, fallback: Iterable[float] = (1.0, 0.0, 0.0)) -> np.ndarray:
    n = norm(values)
    if n < 1e-12:
        return np.array(list(fallback), dtype=float)
    return values / n


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def wrap_pi(angle_rad: float) -> float:
    return (float(angle_rad) + math.pi) % (2.0 * math.pi) - math.pi


def deep_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    return float(value)

