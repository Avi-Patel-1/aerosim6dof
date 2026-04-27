"""Vehicle state representation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from aerosim6dof.core.quaternions import normalize


@dataclass
class VehicleState:
    position_m: np.ndarray
    velocity_mps: np.ndarray
    quaternion: np.ndarray
    rates_rps: np.ndarray
    mass_kg: float

    def copy(self) -> "VehicleState":
        return VehicleState(
            self.position_m.copy(),
            self.velocity_mps.copy(),
            normalize(self.quaternion.copy()),
            self.rates_rps.copy(),
            float(self.mass_kg),
        )

    def pack(self) -> np.ndarray:
        return np.concatenate(
            [
                self.position_m,
                self.velocity_mps,
                normalize(self.quaternion),
                self.rates_rps,
                np.array([self.mass_kg], dtype=float),
            ]
        )

    @classmethod
    def unpack(cls, values: np.ndarray) -> "VehicleState":
        return cls(
            np.array(values[0:3], dtype=float),
            np.array(values[3:6], dtype=float),
            normalize(np.array(values[6:10], dtype=float)),
            np.array(values[10:13], dtype=float),
            float(values[13]),
        )

