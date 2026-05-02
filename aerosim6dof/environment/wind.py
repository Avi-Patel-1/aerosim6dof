"""Wind, shear, gust, and turbulence models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from aerosim6dof.core.vectors import vec3
from aerosim6dof.physics.realism import log_wind_profile, power_law_wind_profile

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
        self.turbulence_cfg = turb
        if turb.get("enabled", False):
            self.turbulence = DrydenApproximation(
                intensity_mps=vec3(turb.get("intensity_mps"), (0.8, 0.8, 0.4)),
                length_scale_m=float(turb.get("length_scale_m", 80.0)),
            )

    def sample(self, t: float, position_m: np.ndarray, airspeed_mps: float, dt: float) -> WindSample:
        steady = vec3(self.config.get("steady_mps"), (0.0, 0.0, 0.0))
        shear = self._shear(position_m, steady)
        sinusoid = self._sinusoidal(t)
        discrete = self._discrete_gust(t)
        turbulence = (
            self.turbulence.sample(self.rng, airspeed_mps, dt)
            if self.turbulence is not None
            else np.zeros(3, dtype=float)
        )
        return WindSample(steady + shear + sinusoid + discrete + turbulence, turbulence)

    def deterministic(self, t: float, position_m: np.ndarray) -> np.ndarray:
        steady = vec3(self.config.get("steady_mps"), (0.0, 0.0, 0.0))
        return (
            steady
            + self._shear(position_m, steady)
            + self._sinusoidal(t)
            + self._discrete_gust(t)
        )

    def _shear(self, position_m: np.ndarray, steady_mps: np.ndarray | None = None) -> np.ndarray:
        shear = self.config.get("shear", {})
        if not shear:
            legacy = self.config.get("gust", {}).get("vertical_shear", 0.0)
            return np.array([float(legacy) * max(position_m[2], 0.0) / 1000.0, 0.0, 0.0], dtype=float)
        model = str(shear.get("model", shear.get("type", "gradient"))).lower()
        if model in {"power_law", "power-law"}:
            reference = vec3(shear.get("reference_wind_mps"), tuple(steady_mps if steady_mps is not None else np.zeros(3)))
            profiled = power_law_wind_profile(
                float(position_m[2]),
                reference,
                reference_altitude_m=float(shear.get("reference_altitude_m", 10.0)),
                shear_exponent=float(shear.get("shear_exponent", shear.get("exponent", 0.14))),
                ground_altitude_m=float(shear.get("ground_altitude_m", 0.0)),
            )
            return profiled - (steady_mps if steady_mps is not None else np.zeros(3))
        if model in {"log", "log_law", "log-law"}:
            reference = vec3(shear.get("reference_wind_mps"), tuple(steady_mps if steady_mps is not None else np.zeros(3)))
            profiled = log_wind_profile(
                float(position_m[2]),
                reference,
                reference_altitude_m=float(shear.get("reference_altitude_m", 10.0)),
                roughness_length_m=float(shear.get("roughness_length_m", 0.03)),
                displacement_height_m=float(shear.get("displacement_height_m", 0.0)),
            )
            return profiled - (steady_mps if steady_mps is not None else np.zeros(3))
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
