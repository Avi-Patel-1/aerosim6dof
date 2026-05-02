"""Standalone realism helpers for future 6-DOF model integration.

The models in this module are intentionally independent of the current
integrator, runner, vehicle, and CSV telemetry surfaces. They provide small,
deterministic building blocks that can be adopted by those layers later.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np


G0 = 9.80665
R_AIR = 287.05287
GAMMA_AIR = 1.4
SEA_LEVEL_TEMPERATURE_K = 288.15
SEA_LEVEL_PRESSURE_PA = 101_325.0
EPS = 1e-12


@dataclass(frozen=True)
class AtmosphereLayer:
    """Piecewise atmosphere layer starting at ``base_altitude_m``."""

    base_altitude_m: float
    lapse_rate_k_per_m: float


@dataclass(frozen=True)
class AtmosphereSample:
    altitude_m: float
    density_kgpm3: float
    pressure_pa: float
    temperature_k: float
    speed_of_sound_mps: float

    def as_dict(self) -> dict[str, float]:
        return {
            "altitude_m": self.altitude_m,
            "density_kgpm3": self.density_kgpm3,
            "pressure_pa": self.pressure_pa,
            "temperature_k": self.temperature_k,
            "speed_of_sound_mps": self.speed_of_sound_mps,
        }


STANDARD_ATMOSPHERE_LAYERS: tuple[AtmosphereLayer, ...] = (
    AtmosphereLayer(0.0, -0.0065),
    AtmosphereLayer(11_000.0, 0.0),
    AtmosphereLayer(20_000.0, 0.0010),
    AtmosphereLayer(32_000.0, 0.0028),
)


def layered_atmosphere(
    altitude_m: float,
    *,
    temperature_offset_k: float = 0.0,
    pressure_scale: float = 1.0,
    density_scale: float = 1.0,
    min_temperature_k: float = 150.0,
    sea_level_temperature_k: float = SEA_LEVEL_TEMPERATURE_K,
    sea_level_pressure_pa: float = SEA_LEVEL_PRESSURE_PA,
    layers: Sequence[AtmosphereLayer] = STANDARD_ATMOSPHERE_LAYERS,
) -> AtmosphereSample:
    """Return a layered hydrostatic atmosphere with simple weather adjustments.

    ``temperature_offset_k``, ``pressure_scale``, and ``density_scale`` are
    applied after the base hydrostatic state is evaluated. Negative altitude is
    clamped to sea level because the simulator uses z-up altitude telemetry.
    """

    h = max(0.0, _finite_float(altitude_m, "altitude_m"))
    temp0 = _positive_float(sea_level_temperature_k, "sea_level_temperature_k")
    pressure0 = _positive_float(sea_level_pressure_pa, "sea_level_pressure_pa")
    pressure_factor = _nonnegative_float(pressure_scale, "pressure_scale")
    density_factor = _nonnegative_float(density_scale, "density_scale")
    min_temp = _positive_float(min_temperature_k, "min_temperature_k")
    temp_offset = _finite_float(temperature_offset_k, "temperature_offset_k")

    temperature, pressure = _standard_layer_state(h, temp0, pressure0, layers)
    adjusted_temperature = max(min_temp, temperature + temp_offset)
    adjusted_pressure = pressure * pressure_factor
    density = adjusted_pressure / (R_AIR * adjusted_temperature) * density_factor
    speed_of_sound = math.sqrt(GAMMA_AIR * R_AIR * adjusted_temperature)
    return AtmosphereSample(h, density, adjusted_pressure, adjusted_temperature, speed_of_sound)


def power_law_wind_profile(
    altitude_m: float,
    reference_wind_mps: float | Sequence[float] | np.ndarray,
    *,
    reference_altitude_m: float = 10.0,
    shear_exponent: float = 0.14,
    ground_altitude_m: float = 0.0,
    minimum_height_m: float = 0.5,
) -> np.ndarray:
    """Scale a reference wind vector with the atmospheric power-law profile."""

    wind = _as_vector(reference_wind_mps, "reference_wind_mps")
    height = max(_finite_float(altitude_m, "altitude_m") - ground_altitude_m, minimum_height_m)
    ref_height = max(_positive_float(reference_altitude_m, "reference_altitude_m") - ground_altitude_m, minimum_height_m)
    exponent = _nonnegative_float(shear_exponent, "shear_exponent")
    return wind * (height / ref_height) ** exponent


def log_wind_profile(
    altitude_m: float,
    reference_wind_mps: float | Sequence[float] | np.ndarray,
    *,
    reference_altitude_m: float = 10.0,
    roughness_length_m: float = 0.03,
    displacement_height_m: float = 0.0,
) -> np.ndarray:
    """Scale wind with the neutral log-law profile for near-surface shear."""

    wind = _as_vector(reference_wind_mps, "reference_wind_mps")
    roughness = _positive_float(roughness_length_m, "roughness_length_m")
    reference_altitude = _positive_float(reference_altitude_m, "reference_altitude_m")
    displacement = _finite_float(displacement_height_m, "displacement_height_m")
    z_ref = reference_altitude - displacement
    if z_ref <= roughness:
        raise ValueError("reference_altitude_m must be above displacement_height_m + roughness_length_m")
    z = max(_finite_float(altitude_m, "altitude_m") - displacement, roughness * (1.0 + 1e-9))
    scale = math.log(z / roughness) / math.log(z_ref / roughness)
    return wind * max(0.0, scale)


@dataclass(frozen=True)
class TurbulenceProfileSample:
    sigma_mps: np.ndarray
    length_scale_m: np.ndarray


def turbulence_profile(
    altitude_m: float,
    *,
    reference_sigma_mps: float | Sequence[float] | np.ndarray = (1.0, 1.0, 0.5),
    minimum_sigma_mps: float | Sequence[float] | np.ndarray = (0.05, 0.05, 0.03),
    decay_altitude_m: float = 2500.0,
    base_length_scale_m: float = 30.0,
    length_scale_gradient: float = 0.08,
    max_length_scale_m: float = 600.0,
) -> TurbulenceProfileSample:
    """Return altitude-varying turbulence RMS and correlation length scales."""

    h = max(0.0, _finite_float(altitude_m, "altitude_m"))
    sigma_ref = _as_vector(reference_sigma_mps, "reference_sigma_mps")
    sigma_floor = _as_vector(minimum_sigma_mps, "minimum_sigma_mps")
    if np.any(sigma_ref < 0.0) or np.any(sigma_floor < 0.0):
        raise ValueError("turbulence sigma values must be nonnegative")
    decay = _positive_float(decay_altitude_m, "decay_altitude_m")
    base_length = _positive_float(base_length_scale_m, "base_length_scale_m")
    gradient = _nonnegative_float(length_scale_gradient, "length_scale_gradient")
    max_length = _positive_float(max_length_scale_m, "max_length_scale_m")
    if max_length < base_length:
        raise ValueError("max_length_scale_m must be greater than or equal to base_length_scale_m")

    sigma = sigma_floor + (sigma_ref - sigma_floor) * math.exp(-h / decay)
    length = min(max_length, base_length + gradient * h)
    return TurbulenceProfileSample(np.asarray(sigma, dtype=float), np.full(3, length, dtype=float))


@dataclass(frozen=True)
class WindProfileSample:
    steady_wind_mps: np.ndarray
    turbulence_sigma_mps: np.ndarray
    turbulence_length_scale_m: np.ndarray


@dataclass(frozen=True)
class WindShearTurbulenceProfile:
    """Combined helper for steady shear and turbulence envelope lookup."""

    reference_wind_mps: float | Sequence[float] | np.ndarray
    reference_altitude_m: float = 10.0
    shear_exponent: float = 0.14
    reference_sigma_mps: float | Sequence[float] | np.ndarray = (1.0, 1.0, 0.5)
    minimum_sigma_mps: float | Sequence[float] | np.ndarray = (0.05, 0.05, 0.03)

    def sample(self, altitude_m: float) -> WindProfileSample:
        turbulence = turbulence_profile(
            altitude_m,
            reference_sigma_mps=self.reference_sigma_mps,
            minimum_sigma_mps=self.minimum_sigma_mps,
        )
        return WindProfileSample(
            steady_wind_mps=power_law_wind_profile(
                altitude_m,
                self.reference_wind_mps,
                reference_altitude_m=self.reference_altitude_m,
                shear_exponent=self.shear_exponent,
            ),
            turbulence_sigma_mps=turbulence.sigma_mps,
            turbulence_length_scale_m=turbulence.length_scale_m,
        )


@dataclass(frozen=True)
class EngineSpoolSample:
    command: float
    actual: float
    rate_limited: bool
    time_constant_s: float


def engine_spool_step(
    current: float,
    command: float,
    dt: float,
    *,
    spool_up_tau_s: float = 0.5,
    spool_down_tau_s: float = 0.25,
    rate_limit_per_s: float | None = None,
    command_limits: tuple[float, float] = (0.0, 1.0),
) -> EngineSpoolSample:
    """Advance a first-order engine spool state by one time step."""

    step_dt = _nonnegative_float(dt, "dt")
    low, high = _validate_limits(command_limits)
    current_value = min(high, max(low, _finite_float(current, "current")))
    command_value = min(high, max(low, _finite_float(command, "command")))
    tau = _nonnegative_float(spool_up_tau_s if command_value >= current_value else spool_down_tau_s, "spool_tau_s")
    if step_dt <= 0.0:
        return EngineSpoolSample(command_value, current_value, False, tau)

    if tau <= EPS:
        target = command_value
    else:
        target = current_value + (command_value - current_value) * (1.0 - math.exp(-step_dt / tau))

    rate_limited = False
    if rate_limit_per_s is not None:
        rate_limit = _nonnegative_float(rate_limit_per_s, "rate_limit_per_s")
        max_delta = rate_limit * step_dt
        delta = target - current_value
        if abs(delta) > max_delta:
            target = current_value + math.copysign(max_delta, delta)
            rate_limited = True

    actual = min(high, max(low, target))
    return EngineSpoolSample(command_value, actual, rate_limited, tau)


class EngineSpool:
    """Stateful wrapper around :func:`engine_spool_step`."""

    def __init__(
        self,
        *,
        initial: float = 0.0,
        spool_up_tau_s: float = 0.5,
        spool_down_tau_s: float = 0.25,
        rate_limit_per_s: float | None = None,
        command_limits: tuple[float, float] = (0.0, 1.0),
    ):
        self.spool_up_tau_s = spool_up_tau_s
        self.spool_down_tau_s = spool_down_tau_s
        self.rate_limit_per_s = rate_limit_per_s
        self.command_limits = command_limits
        low, high = _validate_limits(command_limits)
        self.actual = min(high, max(low, _finite_float(initial, "initial")))

    def step(self, command: float, dt: float) -> EngineSpoolSample:
        sample = engine_spool_step(
            self.actual,
            command,
            dt,
            spool_up_tau_s=self.spool_up_tau_s,
            spool_down_tau_s=self.spool_down_tau_s,
            rate_limit_per_s=self.rate_limit_per_s,
            command_limits=self.command_limits,
        )
        self.actual = sample.actual
        return sample


@dataclass(frozen=True)
class BurnDownSample:
    mass_kg: float
    dry_mass_kg: float
    fuel_remaining_kg: float
    fuel_fraction: float
    inertia_kgm2: np.ndarray


@dataclass(frozen=True)
class FuelMassInertiaModel:
    """Linear fuel burn-down helper for mass and inertia interpolation."""

    initial_mass_kg: float
    dry_mass_kg: float
    initial_inertia_kgm2: Sequence[Sequence[float]] | np.ndarray
    dry_inertia_kgm2: Sequence[Sequence[float]] | np.ndarray

    def __post_init__(self) -> None:
        initial_mass = _positive_float(self.initial_mass_kg, "initial_mass_kg")
        dry_mass = _positive_float(self.dry_mass_kg, "dry_mass_kg")
        if dry_mass > initial_mass:
            raise ValueError("dry_mass_kg must be less than or equal to initial_mass_kg")
        object.__setattr__(self, "initial_mass_kg", initial_mass)
        object.__setattr__(self, "dry_mass_kg", dry_mass)
        object.__setattr__(self, "initial_inertia_kgm2", _matrix3(self.initial_inertia_kgm2, "initial_inertia_kgm2"))
        object.__setattr__(self, "dry_inertia_kgm2", _matrix3(self.dry_inertia_kgm2, "dry_inertia_kgm2"))

    def step(self, current_mass_kg: float, mass_flow_kgps: float, dt: float) -> BurnDownSample:
        current_mass = _finite_float(current_mass_kg, "current_mass_kg")
        mass_flow = _nonnegative_float(mass_flow_kgps, "mass_flow_kgps")
        step_dt = _nonnegative_float(dt, "dt")
        return self.state_for_mass(current_mass - mass_flow * step_dt)

    def state_for_mass(self, mass_kg: float) -> BurnDownSample:
        mass = min(self.initial_mass_kg, max(self.dry_mass_kg, _finite_float(mass_kg, "mass_kg")))
        usable_fuel = max(self.initial_mass_kg - self.dry_mass_kg, 0.0)
        fuel_remaining = max(mass - self.dry_mass_kg, 0.0)
        fuel_fraction = fuel_remaining / usable_fuel if usable_fuel > EPS else 0.0
        inertia = self.dry_inertia_kgm2 + fuel_fraction * (self.initial_inertia_kgm2 - self.dry_inertia_kgm2)
        inertia = 0.5 * (inertia + inertia.T)
        return BurnDownSample(mass, self.dry_mass_kg, fuel_remaining, fuel_fraction, inertia.copy())


@dataclass(frozen=True)
class ActuatorCommandSample:
    raw_command: float
    delayed_command: float
    shaped_target: float
    output: float
    saturated: bool
    rate_limited: bool
    in_backlash: bool


class ActuatorCommandShaper:
    """Apply delay, deadband, saturation, backlash, and rate limiting to a scalar command."""

    def __init__(
        self,
        *,
        limit: float | tuple[float, float] = (-1.0, 1.0),
        rate_limit_per_s: float | None = None,
        delay_s: float = 0.0,
        deadband: float = 0.0,
        backlash: float = 0.0,
        initial_output: float = 0.0,
    ):
        self.low, self.high = _validate_symmetric_or_pair_limit(limit)
        self.rate_limit_per_s = None if rate_limit_per_s is None else _nonnegative_float(rate_limit_per_s, "rate_limit_per_s")
        self.delay_s = _nonnegative_float(delay_s, "delay_s")
        self.deadband = _nonnegative_float(deadband, "deadband")
        self.backlash = _nonnegative_float(backlash, "backlash")
        self.output = min(self.high, max(self.low, _finite_float(initial_output, "initial_output")))
        self._initial_command = self.output
        self._time = 0.0
        self._last_t = -math.inf
        self._history: deque[tuple[float, float]] = deque()

    def step(self, command: float, dt: float, t: float | None = None) -> ActuatorCommandSample:
        step_dt = _nonnegative_float(dt, "dt")
        now = self._time + step_dt if t is None else _finite_float(t, "t")
        if now + EPS < self._last_t:
            raise ValueError("actuator command times must be monotonic")
        self._time = now
        self._last_t = now

        raw = _finite_float(command, "command")
        self._history.append((now, raw))
        self._trim_history(now)
        delayed = self._delayed_command(now)
        after_deadband = 0.0 if abs(delayed) < self.deadband else delayed
        shaped_target = min(self.high, max(self.low, after_deadband))
        saturated = abs(after_deadband - shaped_target) > 1e-12

        backlash_target, in_backlash = self._apply_backlash(shaped_target)
        output, rate_limited = self._apply_rate_limit(backlash_target, step_dt)
        self.output = min(self.high, max(self.low, output))
        return ActuatorCommandSample(raw, delayed, shaped_target, self.output, saturated, rate_limited, in_backlash)

    def _delayed_command(self, now: float) -> float:
        if not self._history:
            return self._initial_command
        if self.delay_s <= EPS:
            return self._history[-1][1]
        target_time = now - self.delay_s
        selected = self._initial_command
        for sample_t, command in self._history:
            if sample_t <= target_time + EPS:
                selected = command
            else:
                break
        return selected

    def _trim_history(self, now: float) -> None:
        retain_s = max(self.delay_s + 1.0, 1.0)
        while len(self._history) > 2 and self._history[1][0] < now - retain_s:
            self._history.popleft()

    def _apply_backlash(self, target: float) -> tuple[float, bool]:
        if self.backlash <= EPS:
            return target, False
        gap = target - self.output
        if gap > self.backlash:
            return target - self.backlash, False
        if gap < -self.backlash:
            return target + self.backlash, False
        return self.output, abs(gap) > EPS

    def _apply_rate_limit(self, target: float, dt: float) -> tuple[float, bool]:
        if self.rate_limit_per_s is None:
            return target, False
        delta = target - self.output
        max_delta = self.rate_limit_per_s * dt
        if abs(delta) <= max_delta + EPS:
            return target, False
        return self.output + math.copysign(max_delta, delta), True


@dataclass(frozen=True)
class SensorLatencyBiasSample:
    value: np.ndarray
    delayed_value: np.ndarray
    bias: np.ndarray
    latency_s: float


class LatencyBuffer:
    """Timestamped vector buffer with linear interpolation lookup."""

    def __init__(self, *, latency_s: float = 0.0, retain_s: float | None = None):
        self.latency_s = _nonnegative_float(latency_s, "latency_s")
        self.retain_s = retain_s
        if retain_s is not None:
            _positive_float(retain_s, "retain_s")
        self._samples: deque[tuple[float, np.ndarray]] = deque()

    def add(self, t: float, value: float | Sequence[float] | np.ndarray) -> None:
        sample_t = _finite_float(t, "t")
        sample_value = np.asarray(value, dtype=float).copy()
        if sample_value.size == 0 or not np.all(np.isfinite(sample_value)):
            raise ValueError("value must contain finite numbers")
        if self._samples and sample_t + EPS < self._samples[-1][0]:
            raise ValueError("latency samples must be monotonic")
        if self._samples and sample_value.shape != self._samples[-1][1].shape:
            raise ValueError("latency samples must keep a consistent shape")
        self._samples.append((sample_t, sample_value))
        self._trim(sample_t)

    def sample(self, t: float) -> np.ndarray:
        if not self._samples:
            raise ValueError("latency buffer is empty")
        target_t = _finite_float(t, "t") - self.latency_s
        if target_t <= self._samples[0][0]:
            return self._samples[0][1].copy()
        if target_t >= self._samples[-1][0]:
            return self._samples[-1][1].copy()
        previous_t, previous_value = self._samples[0]
        for next_t, next_value in list(self._samples)[1:]:
            if next_t >= target_t:
                span = max(next_t - previous_t, EPS)
                alpha = (target_t - previous_t) / span
                return previous_value + alpha * (next_value - previous_value)
            previous_t, previous_value = next_t, next_value
        return self._samples[-1][1].copy()

    def _trim(self, now: float) -> None:
        retain_s = self.retain_s if self.retain_s is not None else max(self.latency_s + 1.0, 1.0)
        while len(self._samples) > 2 and self._samples[1][0] < now - retain_s:
            self._samples.popleft()


class SensorLatencyBias:
    """Apply measurement latency and slowly drifting additive bias."""

    def __init__(
        self,
        *,
        latency_s: float = 0.0,
        initial_bias: float | Sequence[float] | np.ndarray = 0.0,
        drift_rate_per_s: float | Sequence[float] | np.ndarray = 0.0,
        random_walk_std_per_sqrt_s: float | Sequence[float] | np.ndarray = 0.0,
        bias_limit: float | Sequence[float] | np.ndarray | None = None,
    ):
        self.buffer = LatencyBuffer(latency_s=latency_s)
        self.bias = np.asarray(initial_bias, dtype=float).copy()
        if self.bias.size == 0 or not np.all(np.isfinite(self.bias)):
            raise ValueError("initial_bias must contain finite numbers")
        self.drift_rate_per_s = _broadcast_like(drift_rate_per_s, self.bias, "drift_rate_per_s")
        self.random_walk_std_per_sqrt_s = _broadcast_like(
            random_walk_std_per_sqrt_s,
            self.bias,
            "random_walk_std_per_sqrt_s",
        )
        if np.any(self.random_walk_std_per_sqrt_s < 0.0):
            raise ValueError("random_walk_std_per_sqrt_s must be nonnegative")
        self.bias_limit = None if bias_limit is None else np.abs(_broadcast_like(bias_limit, self.bias, "bias_limit"))

    def sample(
        self,
        t: float,
        value: float | Sequence[float] | np.ndarray,
        dt: float,
        rng: np.random.Generator | None = None,
    ) -> SensorLatencyBiasSample:
        step_dt = _nonnegative_float(dt, "dt")
        sample_value = np.asarray(value, dtype=float).copy()
        if sample_value.shape != self.bias.shape:
            if self.bias.shape == () and sample_value.shape != ():
                self.bias = np.full(sample_value.shape, float(self.bias), dtype=float)
                self.drift_rate_per_s = _broadcast_like(self.drift_rate_per_s, self.bias, "drift_rate_per_s")
                self.random_walk_std_per_sqrt_s = _broadcast_like(
                    self.random_walk_std_per_sqrt_s,
                    self.bias,
                    "random_walk_std_per_sqrt_s",
                )
                if self.bias_limit is not None:
                    self.bias_limit = _broadcast_like(self.bias_limit, self.bias, "bias_limit")
            elif sample_value.shape != self.bias.shape:
                raise ValueError("value shape must match bias shape")

        self.buffer.add(t, sample_value)
        self._advance_bias(step_dt, rng)
        delayed = self.buffer.sample(t)
        measured = delayed + self.bias
        return SensorLatencyBiasSample(measured.copy(), delayed.copy(), self.bias.copy(), self.buffer.latency_s)

    def _advance_bias(self, dt: float, rng: np.random.Generator | None) -> None:
        self.bias = self.bias + self.drift_rate_per_s * dt
        if rng is not None and np.any(self.random_walk_std_per_sqrt_s > 0.0):
            self.bias = self.bias + rng.normal(0.0, self.random_walk_std_per_sqrt_s * math.sqrt(dt), self.bias.shape)
        if self.bias_limit is not None:
            self.bias = np.clip(self.bias, -self.bias_limit, self.bias_limit)


def _standard_layer_state(
    altitude_m: float,
    sea_level_temperature_k: float,
    sea_level_pressure_pa: float,
    layers: Sequence[AtmosphereLayer],
) -> tuple[float, float]:
    validated = _validate_layers(layers)
    temperature = sea_level_temperature_k
    pressure = sea_level_pressure_pa
    for index, layer in enumerate(validated):
        next_altitude = validated[index + 1].base_altitude_m if index + 1 < len(validated) else math.inf
        if altitude_m <= next_altitude:
            return _advance_atmosphere_layer(temperature, pressure, altitude_m - layer.base_altitude_m, layer.lapse_rate_k_per_m)
        temperature, pressure = _advance_atmosphere_layer(
            temperature,
            pressure,
            next_altitude - layer.base_altitude_m,
            layer.lapse_rate_k_per_m,
        )
    return temperature, pressure


def _advance_atmosphere_layer(
    base_temperature_k: float,
    base_pressure_pa: float,
    delta_altitude_m: float,
    lapse_rate_k_per_m: float,
) -> tuple[float, float]:
    lapse = _finite_float(lapse_rate_k_per_m, "lapse_rate_k_per_m")
    delta = _nonnegative_float(delta_altitude_m, "delta_altitude_m")
    if abs(lapse) <= EPS:
        pressure = base_pressure_pa * math.exp(-G0 * delta / (R_AIR * base_temperature_k))
        return base_temperature_k, pressure
    temperature = base_temperature_k + lapse * delta
    if temperature <= 0.0:
        raise ValueError("atmosphere layer produced nonpositive temperature")
    pressure = base_pressure_pa * (temperature / base_temperature_k) ** (-G0 / (lapse * R_AIR))
    return temperature, pressure


def _validate_layers(layers: Sequence[AtmosphereLayer]) -> tuple[AtmosphereLayer, ...]:
    if not layers:
        raise ValueError("at least one atmosphere layer is required")
    validated: list[AtmosphereLayer] = []
    previous_altitude = -math.inf
    for raw in layers:
        layer = raw if isinstance(raw, AtmosphereLayer) else AtmosphereLayer(*raw)
        base_altitude = _finite_float(layer.base_altitude_m, "layer.base_altitude_m")
        lapse = _finite_float(layer.lapse_rate_k_per_m, "layer.lapse_rate_k_per_m")
        if base_altitude < 0.0:
            raise ValueError("atmosphere layer base altitude must be nonnegative")
        if base_altitude <= previous_altitude:
            raise ValueError("atmosphere layers must be sorted by increasing base altitude")
        validated.append(AtmosphereLayer(base_altitude, lapse))
        previous_altitude = base_altitude
    if abs(validated[0].base_altitude_m) > EPS:
        raise ValueError("first atmosphere layer must start at 0 m")
    return tuple(validated)


def _finite_float(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _positive_float(value: float, name: str) -> float:
    result = _finite_float(value, name)
    if result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


def _nonnegative_float(value: float, name: str) -> float:
    result = _finite_float(value, name)
    if result < 0.0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _as_vector(value: float | Sequence[float] | np.ndarray, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.shape == ():
        arr = np.full(3, float(arr), dtype=float)
    if arr.shape != (3,) or not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be a finite scalar or 3-vector")
    return arr.copy()


def _matrix3(value: Sequence[Sequence[float]] | np.ndarray, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.shape != (3, 3) or not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be a finite 3x3 matrix")
    return arr.copy()


def _broadcast_like(value: float | Sequence[float] | np.ndarray, target: np.ndarray, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.shape == ():
        arr = np.full(target.shape, float(arr), dtype=float)
    if arr.shape != target.shape or not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite and broadcastable to shape {target.shape}")
    return arr.copy()


def _validate_limits(command_limits: tuple[float, float]) -> tuple[float, float]:
    low, high = (_finite_float(command_limits[0], "command_limits[0]"), _finite_float(command_limits[1], "command_limits[1]"))
    if low >= high:
        raise ValueError("command_limits must be increasing")
    return low, high


def _validate_symmetric_or_pair_limit(limit: float | tuple[float, float]) -> tuple[float, float]:
    if isinstance(limit, tuple):
        return _validate_limits(limit)
    magnitude = _positive_float(limit, "limit")
    return -magnitude, magnitude
