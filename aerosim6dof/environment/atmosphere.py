"""ISA atmosphere model."""

from __future__ import annotations

import math
from dataclasses import dataclass

from aerosim6dof.constants import (
    G0,
    GAMMA_AIR,
    R_AIR,
    SEA_LEVEL_PRESSURE_PA,
    SEA_LEVEL_TEMPERATURE_K,
    TROPOPAUSE_M,
    TROPOSPHERE_LAPSE_K_PER_M,
)


@dataclass(frozen=True)
class AtmosphereState:
    density: float
    pressure: float
    temperature: float
    speed_of_sound: float

    def as_dict(self) -> dict[str, float]:
        return {
            "density": self.density,
            "pressure": self.pressure,
            "temperature": self.temperature,
            "speed_of_sound": self.speed_of_sound,
        }


def isa_atmosphere(altitude_m: float) -> AtmosphereState:
    h = max(0.0, float(altitude_m))
    t0 = SEA_LEVEL_TEMPERATURE_K
    p0 = SEA_LEVEL_PRESSURE_PA
    lapse = TROPOSPHERE_LAPSE_K_PER_M
    if h <= TROPOPAUSE_M:
        temp = t0 + lapse * h
        pressure = p0 * (temp / t0) ** (-G0 / (lapse * R_AIR))
    else:
        t11 = t0 + lapse * TROPOPAUSE_M
        p11 = p0 * (t11 / t0) ** (-G0 / (lapse * R_AIR))
        temp = t11
        pressure = p11 * math.exp(-G0 * (h - TROPOPAUSE_M) / (R_AIR * temp))
    density = pressure / (R_AIR * temp)
    speed_of_sound = math.sqrt(GAMMA_AIR * R_AIR * temp)
    return AtmosphereState(density, pressure, temp, speed_of_sound)


def atmosphere(altitude_m: float) -> dict[str, float]:
    return isa_atmosphere(altitude_m).as_dict()

