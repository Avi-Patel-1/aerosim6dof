"""Controller primitives."""

from __future__ import annotations

from dataclasses import dataclass

from aerosim6dof.core.vectors import clamp


@dataclass
class PID:
    kp: float
    ki: float
    kd: float
    limit: float
    integrator_limit: float = 1.0

    def __post_init__(self) -> None:
        self.integral = 0.0
        self.prev_error = 0.0

    def reset(self) -> None:
        self.integral = 0.0
        self.prev_error = 0.0

    def step(self, error: float, dt: float, schedule: float = 1.0) -> float:
        self.integral = clamp(self.integral + float(error) * dt, -self.integrator_limit, self.integrator_limit)
        derivative = (float(error) - self.prev_error) / max(dt, 1e-9)
        self.prev_error = float(error)
        value = schedule * self.kp * error + self.ki * self.integral + self.kd * derivative
        saturated = clamp(value, -abs(self.limit), abs(self.limit))
        if value != saturated and self.ki != 0.0:
            self.integral -= float(error) * dt * 0.5
        return saturated


def pid_from_config(config: dict[str, float], default: dict[str, float]) -> PID:
    merged = {**default, **(config or {})}
    return PID(
        kp=float(merged.get("kp", 0.0)),
        ki=float(merged.get("ki", 0.0)),
        kd=float(merged.get("kd", 0.0)),
        limit=float(merged.get("limit", 0.3)),
        integrator_limit=float(merged.get("integrator_limit", 1.0)),
    )

