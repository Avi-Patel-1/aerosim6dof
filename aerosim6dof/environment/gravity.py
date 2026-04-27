"""Altitude-dependent gravity."""

from __future__ import annotations

import numpy as np

from aerosim6dof.constants import EARTH_RADIUS_M, G0


def gravity_magnitude(altitude_m: float) -> float:
    r = EARTH_RADIUS_M + max(0.0, float(altitude_m))
    return G0 * (EARTH_RADIUS_M / r) ** 2


def gravity_vector(altitude_m: float) -> np.ndarray:
    return np.array([0.0, 0.0, -gravity_magnitude(altitude_m)], dtype=float)

