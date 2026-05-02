"""Atmosphere models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from aerosim6dof.constants import (
    G0,
    GAMMA_AIR,
    R_AIR,
    SEA_LEVEL_PRESSURE_PA,
    SEA_LEVEL_TEMPERATURE_K,
    TROPOPAUSE_M,
    TROPOSPHERE_LAPSE_K_PER_M,
)
from aerosim6dof.physics.realism import AtmosphereLayer, layered_atmosphere


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


class AtmosphereModel:
    """Configurable atmosphere wrapper used by the runtime dynamics model."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.model = str(self.config.get("model", self.config.get("type", "isa"))).lower()
        self.temperature_offset_k = float(self.config.get("temperature_offset_k", self.config.get("temperature_delta_k", 0.0)))
        self.pressure_scale = float(self.config.get("pressure_scale", 1.0))
        self.density_scale = float(self.config.get("density_scale", 1.0))
        self.min_temperature_k = float(self.config.get("min_temperature_k", 150.0))
        self.layers = _layers_from_config(self.config.get("layers"))

    def sample(self, altitude_m: float) -> AtmosphereState:
        if self.model in {"layered", "standard_layers", "weather", "realistic"} or self._has_weather_adjustment:
            layer_kwargs = {"layers": self.layers} if self.layers else {}
            sample = layered_atmosphere(
                altitude_m,
                temperature_offset_k=self.temperature_offset_k,
                pressure_scale=self.pressure_scale,
                density_scale=self.density_scale,
                min_temperature_k=self.min_temperature_k,
                **layer_kwargs,
            )
            return AtmosphereState(
                density=sample.density_kgpm3,
                pressure=sample.pressure_pa,
                temperature=sample.temperature_k,
                speed_of_sound=sample.speed_of_sound_mps,
            )
        return isa_atmosphere(altitude_m)

    @property
    def _has_weather_adjustment(self) -> bool:
        return (
            abs(self.temperature_offset_k) > 1e-12
            or abs(self.pressure_scale - 1.0) > 1e-12
            or abs(self.density_scale - 1.0) > 1e-12
            or self.config.get("layers") is not None
        )


def _layers_from_config(raw: Any) -> tuple[AtmosphereLayer, ...]:
    if raw in (None, []):
        return tuple()
    layers: list[AtmosphereLayer] = []
    if not isinstance(raw, list):
        return tuple()
    for item in raw:
        try:
            if isinstance(item, dict):
                layers.append(
                    AtmosphereLayer(
                        base_altitude_m=float(item.get("base_altitude_m", item.get("altitude_m", 0.0))),
                        lapse_rate_k_per_m=float(item.get("lapse_rate_k_per_m", item.get("lapse_k_per_m", 0.0))),
                    )
                )
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                layers.append(AtmosphereLayer(float(item[0]), float(item[1])))
        except (TypeError, ValueError):
            return tuple()
    return tuple(layers)


def atmosphere(altitude_m: float) -> dict[str, float]:
    return isa_atmosphere(altitude_m).as_dict()
