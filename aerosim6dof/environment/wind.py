"""Wind, shear, gust, and turbulence models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from aerosim6dof.core.vectors import vec3

from .turbulence import DrydenApproximation


@dataclass(frozen=True)
class WindSample:
    velocity_mps: np.ndarray
    turbulence_mps: np.ndarray


class WindModel:
    def __init__(self, config: dict[str, Any] | None = None, seed: int = 11):
        self.config = config or {}
        self.rng = np.random.default_rng(int(self.config.get("seed", seed)))
        turb = self.config.get("turbulence", {})
        self.turbulence: DrydenApproximation | None = None
        if turb.get("enabled", False):
            self.turbulence = DrydenApproximation(
                intensity_mps=vec3(turb.get("intensity_mps"), (0.8, 0.8, 0.4)),
                length_scale_m=float(turb.get("length_scale_m", 80.0)),
            )

    def sample(self, t: float, position_m: np.ndarray, airspeed_mps: float, dt: float) -> WindSample:
        steady = vec3(self.config.get("steady_mps"), (0.0, 0.0, 0.0))
        shear = self._shear(position_m)
        sinusoid = self._sinusoidal(t)
        discrete = self._discrete_gust(t)
        turbulence = (
            self.turbulence.sample(self.rng, airspeed_mps, dt)
            if self.turbulence is not None
            else np.zeros(3, dtype=float)
        )
        return WindSample(steady + shear + sinusoid + discrete + turbulence, turbulence)

    def deterministic(self, t: float, position_m: np.ndarray) -> np.ndarray:
        return (
            vec3(self.config.get("steady_mps"), (0.0, 0.0, 0.0))
            + self._shear(position_m)
            + self._sinusoidal(t)
            + self._discrete_gust(t)
        )

    def _shear(self, position_m: np.ndarray) -> np.ndarray:
        shear = self.config.get("shear", {})
        if not shear:
            legacy = self.config.get("gust", {}).get("vertical_shear", 0.0)
            return np.array([float(legacy) * max(position_m[2], 0.0) / 1000.0, 0.0, 0.0], dtype=float)
        gradient = vec3(shear.get("gradient_mps_per_km"), (0.0, 0.0, 0.0))
        reference_alt = float(shear.get("reference_altitude_m", 0.0))
        return gradient * max(position_m[2] - reference_alt, 0.0) / 1000.0

    def _sinusoidal(self, t: float) -> np.ndarray:
        gust = self.config.get("sinusoidal_gust", self.config.get("gust", {}))
        if not gust:
            return np.zeros(3, dtype=float)
        amp = vec3(gust.get("amplitude_mps"), (0.0, 0.0, 0.0))
        freq = float(gust.get("frequency_hz", 0.5))
        phase = float(gust.get("phase_rad", 0.0))
        return amp * math.sin(2.0 * math.pi * freq * t + phase)

    def _discrete_gust(self, t: float) -> np.ndarray:
        gust = self.config.get("discrete_gust", {})
        if not gust:
            return np.zeros(3, dtype=float)
        start = float(gust.get("start_s", 0.0))
        duration = max(1e-6, float(gust.get("duration_s", 1.0)))
        if t < start or t > start + duration:
            return np.zeros(3, dtype=float)
        amp = vec3(gust.get("amplitude_mps"), (0.0, 0.0, 0.0))
        x = (t - start) / duration
        return amp * 0.5 * (1.0 - math.cos(2.0 * math.pi * x))

