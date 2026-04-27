"""Guidance command generation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from aerosim6dof.core.quaternions import to_euler
from aerosim6dof.core.vectors import clamp, vec3, wrap_pi


@dataclass(frozen=True)
class GuidanceCommand:
    roll_rad: float
    pitch_rad: float
    heading_rad: float
    throttle: float
    target_distance_m: float
    mode: str


class GuidanceModel:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.mode = str(self.config.get("mode", "fixed_pitch"))

    def command(self, t: float, state: Any, nav: dict[str, Any]) -> GuidanceCommand:
        roll, pitch, yaw = to_euler(state.quaternion)
        throttle = float(self.config.get("throttle", 0.85))
        target_distance = float("nan")
        pitch_cmd = math.radians(float(self.config.get("pitch_command_deg", 12.0)))
        heading_cmd = math.radians(float(self.config.get("heading_command_deg", 0.0)))
        roll_cmd = math.radians(float(self.config.get("roll_command_deg", 0.0)))
        if self.mode == "pitch_program":
            table = self.config.get("pitch_program", [[0.0, math.degrees(pitch_cmd)]])
            pitch_cmd = math.radians(_interp_pairs(t, table))
        elif self.mode == "altitude_hold":
            target_alt = float(self.config.get("target_altitude_m", state.position_m[2]))
            err = target_alt - float(nav["position_m"][2])
            pitch_cmd = math.radians(clamp(float(self.config.get("trim_pitch_deg", 4.0)) + 0.015 * err, -15.0, 25.0))
        elif self.mode in {"waypoint", "target_intercept", "proportional_navigation"}:
            target = vec3(self.config.get("target_position_m"), (state.position_m[0] + 1000.0, 0.0, state.position_m[2]))
            rel = target - nav["position_m"]
            target_distance = float(np.linalg.norm(rel))
            heading_cmd = math.atan2(float(rel[1]), max(1e-9, float(rel[0])))
            desired_climb = math.atan2(float(rel[2]), max(1.0, float(np.linalg.norm(rel[:2]))))
            pitch_cmd = clamp(desired_climb, math.radians(-15.0), math.radians(25.0))
            if self.mode == "proportional_navigation":
                closing = max(1.0, float(np.linalg.norm(nav["velocity_mps"])))
                pitch_cmd = clamp(pitch_cmd + 0.2 * wrap_pi(desired_climb - pitch), math.radians(-20.0), math.radians(28.0))
                throttle = clamp(throttle + 0.08 * min(1.0, target_distance / closing / 10.0), 0.0, 1.0)
        elif self.mode == "heading_hold":
            heading_cmd = math.radians(float(self.config.get("heading_command_deg", math.degrees(yaw))))
        return GuidanceCommand(roll_cmd, pitch_cmd, heading_cmd, clamp(throttle, 0.0, 1.0), target_distance, self.mode)


def _interp_pairs(x: float, pairs: list[list[float]]) -> float:
    rows = sorted((float(a), float(b)) for a, b in pairs)
    if x <= rows[0][0]:
        return rows[0][1]
    for (x0, y0), (x1, y1) in zip(rows, rows[1:]):
        if x <= x1:
            f = (x - x0) / max(x1 - x0, 1e-12)
            return y0 + f * (y1 - y0)
    return rows[-1][1]

