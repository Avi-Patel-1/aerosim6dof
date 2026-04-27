"""Pitot-static airspeed model."""

from __future__ import annotations

from typing import Any

import numpy as np


class PitotSensor:
    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.noise = float(cfg.get("noise_std_mps", 0.4))
        self.bias = float(cfg.get("bias_mps", 0.0))
        self.qbar_noise_fraction = float(cfg.get("qbar_noise_fraction", 0.01))
        self.compressibility = str(cfg.get("compressibility", cfg.get("compressibility_model", "none")))
        self.blockage_fraction = min(1.0, max(0.0, float(cfg.get("blockage_fraction", 0.0))))

    def sample(
        self,
        rng: np.random.Generator,
        airspeed_mps: float,
        qbar_pa: float,
        mach: float = 0.0,
        extra_bias_mps: float = 0.0,
        dropout: bool = False,
    ) -> dict[str, float]:
        if dropout:
            return {"pitot_valid": 0.0}
        correction = _compressibility_factor(self.compressibility, mach)
        blocked = 1.0 - self.blockage_fraction
        measured_airspeed = max(0.0, airspeed_mps * correction * blocked + self.bias + extra_bias_mps + rng.normal(0.0, self.noise))
        measured_qbar = max(
            0.0,
            qbar_pa * correction * correction * blocked
            + rng.normal(0.0, max(1.0, abs(qbar_pa) * self.qbar_noise_fraction)),
        )
        return {
            "pitot_valid": 1.0,
            "pitot_airspeed_mps": float(measured_airspeed),
            "pitot_qbar_pa": float(measured_qbar),
            "pitot_compressibility_factor": float(correction),
        }


def _compressibility_factor(model: str, mach: float) -> float:
    if model in {"none", "off", ""}:
        return 1.0
    m = max(0.0, min(0.95, float(mach)))
    if model in {"subsonic", "isentropic"}:
        return (1.0 + 0.2 * m * m) ** 1.25
    if model in {"linearized", "prandtl_glauert"}:
        return 1.0 / max(0.35, (1.0 - m * m) ** 0.25)
    return 1.0
