"""Control-surface actuator models."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from aerosim6dof.core.vectors import clamp

from .failures import active_failure


@dataclass(frozen=True)
class ActuatorOutput:
    value_rad: float
    effective_rad: float
    saturated: bool
    failed: bool


class SurfaceActuator:
    def __init__(self, config: dict[str, Any] | None = None, initial_rad: float = 0.0):
        cfg = config or {}
        self.limit_rad = abs(float(cfg.get("limit_rad", cfg.get("surface_limit_rad", 0.35))))
        self.rate_limit_rps = abs(float(cfg.get("rate_limit_rps", cfg.get("surface_rate_rps", 2.5))))
        self.tau_s = max(0.0, float(cfg.get("time_constant_s", cfg.get("lag_s", 0.04))))
        self.deadband_rad = abs(float(cfg.get("deadband_rad", 0.0)))
        self.bias_rad = float(cfg.get("bias_rad", 0.0))
        self.effectiveness = float(cfg.get("effectiveness", 1.0))
        self.failure = cfg.get("failure", {})
        self.value_rad = float(initial_rad)
        self.command_history: deque[tuple[float, float]] = deque(maxlen=2000)

    def step(self, command_rad: float, dt: float, t: float = 0.0) -> ActuatorOutput:
        self.command_history.append((float(t), float(command_rad)))
        failure = active_failure(self.failure, t)
        failed = bool(failure)
        delayed = float(failure.get("delay_s", 0.0)) if failed else 0.0
        if delayed > 0.0:
            target_time = t - delayed
            eligible = [cmd for cmd_t, cmd in self.command_history if cmd_t <= target_time]
            if eligible:
                command_rad = eligible[-1]
        if failed and failure.get("mode") == "stuck":
            stuck_value = failure.get("value_rad")
            if stuck_value is None:
                stuck_value = self.value_rad
            self.value_rad = clamp(float(stuck_value), -self.limit_rad, self.limit_rad)
            return ActuatorOutput(
                self.value_rad,
                self.value_rad * float(failure.get("effectiveness", self.effectiveness)),
                False,
                True,
            )
        eff = float(failure.get("effectiveness", self.effectiveness)) if failed else self.effectiveness
        cmd = float(command_rad) + self.bias_rad
        if abs(cmd) < self.deadband_rad:
            cmd = 0.0
        limited_cmd = clamp(cmd, -self.limit_rad, self.limit_rad)
        saturated = abs(cmd - limited_cmd) > 1e-9
        rate_delta = clamp(limited_cmd - self.value_rad, -self.rate_limit_rps * dt, self.rate_limit_rps * dt)
        target = self.value_rad + rate_delta
        if self.tau_s > 1e-9:
            alpha = clamp(dt / self.tau_s, 0.0, 1.0)
            self.value_rad = self.value_rad + alpha * (target - self.value_rad)
        else:
            self.value_rad = target
        self.value_rad = clamp(self.value_rad, -self.limit_rad, self.limit_rad)
        return ActuatorOutput(self.value_rad, self.value_rad * eff, saturated, failed)


class RateLimitedActuator:
    """Backward-compatible actuator wrapper used by earlier tests."""

    def __init__(self, limit: float, rate_limit: float, initial: float = 0.0):
        self.model = SurfaceActuator(
            {"limit_rad": abs(float(limit)), "rate_limit_rps": abs(float(rate_limit)), "time_constant_s": 0.0},
            initial_rad=initial,
        )

    @property
    def value(self) -> float:
        return self.model.value_rad

    def step(self, command: float, dt: float) -> float:
        return self.model.step(command, dt).value_rad


class ActuatorSet:
    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        limit_rad = cfg.get("surface_limit_rad", cfg.get("limit_rad"))
        if limit_rad is None and "surface_limit_deg" in cfg:
            limit_rad = float(cfg["surface_limit_deg"]) * 3.141592653589793 / 180.0
        rate_rps = cfg.get("surface_rate_rps", cfg.get("rate_limit_rps"))
        if rate_rps is None and "surface_rate_dps" in cfg:
            rate_rps = float(cfg["surface_rate_dps"]) * 3.141592653589793 / 180.0
        common = {
            "limit_rad": limit_rad if limit_rad is not None else 0.35,
            "rate_limit_rps": rate_rps if rate_rps is not None else 2.5,
            "time_constant_s": cfg.get("time_constant_s", cfg.get("lag_s", 0.04)),
            "deadband_rad": cfg.get("deadband_rad", 0.0),
        }
        surfaces = cfg.get("surfaces", {})
        self.elevator = SurfaceActuator({**common, **surfaces.get("elevator", {})})
        self.aileron = SurfaceActuator({**common, **surfaces.get("aileron", {})})
        self.rudder = SurfaceActuator({**common, **surfaces.get("rudder", {})})

    def step(self, commands: dict[str, float], dt: float, t: float) -> tuple[dict[str, float], dict[str, bool]]:
        outputs = {
            "elevator": self.elevator.step(commands.get("elevator", 0.0), dt, t),
            "aileron": self.aileron.step(commands.get("aileron", 0.0), dt, t),
            "rudder": self.rudder.step(commands.get("rudder", 0.0), dt, t),
        }
        controls = {name: out.effective_rad for name, out in outputs.items()}
        flags = {
            **{f"{name}_saturated": out.saturated for name, out in outputs.items()},
            **{f"{name}_failed": out.failed for name, out in outputs.items()},
            **{f"{name}_raw_rad": out.value_rad for name, out in outputs.items()},
            **{f"{name}_effective_rad": out.effective_rad for name, out in outputs.items()},
        }
        return controls, flags
