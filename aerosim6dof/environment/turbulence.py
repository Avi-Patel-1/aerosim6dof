"""Dryden-like colored turbulence approximation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DrydenApproximation:
    intensity_mps: np.ndarray
    length_scale_m: float = 80.0

    def __post_init__(self) -> None:
        self.state = np.zeros(3, dtype=float)

    def sample(self, rng: np.random.Generator, airspeed_mps: float, dt: float) -> np.ndarray:
        tau = max(0.2, self.length_scale_m / max(airspeed_mps, 1.0))
        phi = float(np.exp(-max(dt, 0.0) / tau))
        sigma = np.sqrt(max(0.0, 1.0 - phi * phi)) * self.intensity_mps
        self.state = phi * self.state + rng.normal(0.0, sigma, 3)
        return self.state.copy()

