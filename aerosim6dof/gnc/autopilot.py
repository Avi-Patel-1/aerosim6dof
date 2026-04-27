"""Autopilot loops."""

from __future__ import annotations

import math
from typing import Any

from aerosim6dof.core.quaternions import to_euler
from aerosim6dof.core.vectors import clamp, wrap_pi

from .control_allocation import allocate
from .controllers import pid_from_config
from .guidance import GuidanceCommand


class Autopilot:
    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.pitch_pid = pid_from_config(cfg.get("pitch_pid", {}), {"kp": 1.6, "ki": 0.02, "kd": 0.25, "limit": 0.35})
        self.yaw_pid = pid_from_config(cfg.get("yaw_pid", {}), {"kp": 1.8, "ki": 0.0, "kd": 0.12, "limit": 0.30})
        self.roll_pid = pid_from_config(cfg.get("roll_pid", {}), {"kp": 3.0, "ki": 0.0, "kd": 0.18, "limit": 0.35})
        self.command_limit_rad = math.radians(float(cfg.get("command_limit_deg", 24.0)))
        self.schedule_qbar_pa = float(cfg.get("schedule_qbar_pa", 30_000.0))
        self.pitch_rate_damping = float(cfg.get("pitch_rate_damping", 0.10))
        self.roll_rate_damping = float(cfg.get("roll_rate_damping", 1.10))
        self.yaw_rate_damping = float(cfg.get("yaw_rate_damping", 0.55))
        self.beta_damping = float(cfg.get("beta_damping", 0.85))

    def command(self, state: Any, guidance: GuidanceCommand, qbar_pa: float, dt: float, beta_rad: float = 0.0) -> dict[str, float]:
        roll, pitch, yaw = to_euler(state.quaternion)
        schedule = clamp(qbar_pa / max(self.schedule_qbar_pa, 1.0), 0.35, 1.8)
        pitch_cmd = -self.pitch_pid.step(wrap_pi(guidance.pitch_rad - pitch), dt, schedule)
        yaw_cmd = self.yaw_pid.step(wrap_pi(guidance.heading_rad - yaw), dt, schedule)
        roll_cmd = -self.roll_pid.step(wrap_pi(guidance.roll_rad - roll), dt, schedule)
        p_rate, q_rate, r_rate = state.rates_rps
        pitch_cmd -= self.pitch_rate_damping * float(q_rate)
        roll_cmd -= self.roll_rate_damping * float(p_rate)
        yaw_cmd += self.yaw_rate_damping * float(r_rate)
        yaw_cmd += self.beta_damping * float(beta_rad)
        surfaces = allocate(
            {"pitch": pitch_cmd, "yaw": yaw_cmd, "roll": roll_cmd},
            {"surface": self.command_limit_rad},
        )
        surfaces["throttle"] = guidance.throttle
        return surfaces
