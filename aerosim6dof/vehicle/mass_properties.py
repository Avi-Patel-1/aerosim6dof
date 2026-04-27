"""Mass and inertia utilities."""

from __future__ import annotations

from typing import Any

import numpy as np


class MassProperties:
    def __init__(self, config: dict[str, Any]):
        self.initial_mass_kg = float(config.get("mass_kg", 18.0))
        self.dry_mass_kg = float(config.get("dry_mass_kg", self.initial_mass_kg * 0.75))
        self.initial_inertia = np.array(
            config.get("inertia_kgm2", [[0.34, 0.0, 0.0], [0.0, 0.88, 0.0], [0.0, 0.0, 0.82]]),
            dtype=float,
        )
        self.dry_inertia = np.array(config.get("dry_inertia_kgm2", self.initial_inertia * 0.82), dtype=float)

    def inertia(self, mass_kg: float) -> np.ndarray:
        if self.initial_mass_kg <= self.dry_mass_kg:
            return self.initial_inertia.copy()
        frac = (float(mass_kg) - self.dry_mass_kg) / (self.initial_mass_kg - self.dry_mass_kg)
        frac = max(0.0, min(1.0, frac))
        mat = self.dry_inertia + frac * (self.initial_inertia - self.dry_inertia)
        return mat + np.eye(3) * 1e-9

