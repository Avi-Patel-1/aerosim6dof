"""Propulsion models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from aerosim6dof.constants import G0
from aerosim6dof.core.interpolation import Table1D
from aerosim6dof.core.vectors import vec3


@dataclass(frozen=True)
class PropulsionSample:
    thrust_body_n: np.ndarray
    moment_body_nm: np.ndarray
    mass_flow_kgps: float
    thrust_n: float
    throttle_command: float = 0.0
    throttle_actual: float = 0.0
    health: str = "off"


class PropulsionModel:
    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.model = str(cfg.get("model", "solid"))
        self.max_thrust_n = float(cfg.get("max_thrust_n", cfg.get("thrust_n", cfg.get("electric_static_thrust_n", 420.0))))
        self.isp_s = float(cfg.get("isp_s", 185.0))
        self.burn_time_s = float(cfg.get("burn_time_s", 12.0))
        self.throttleable = bool(cfg.get("throttleable", True))
        self.min_throttle = float(cfg.get("min_throttle", 0.0))
        self.engine_lag_s = max(0.0, float(cfg.get("engine_lag_s", cfg.get("time_constant_s", 0.0))))
        self.shutdown_intervals = [tuple(float(x) for x in interval) for interval in cfg.get("shutdown_intervals", [])]
        self.restart_allowed = bool(cfg.get("restart_allowed", self.model != "solid"))
        self.ignition_delay_s = max(0.0, float(cfg.get("ignition_delay_s", 0.0)))
        self.actual_throttle = 0.0
        self.position_body_m = vec3(cfg.get("position_body_m"), (0.0, 0.0, 0.0))
        self.misalignment_rad = np.deg2rad(vec3(cfg.get("misalignment_deg"), (0.0, 0.0, 0.0)))
        self.nozzle_cant_moment_nm = vec3(cfg.get("nozzle_cant_moment_nm"), (0.0, 0.0, 0.0))
        self.electric_static_thrust_n = float(cfg.get("electric_static_thrust_n", self.max_thrust_n))
        self.electric_speed_loss = float(cfg.get("electric_speed_loss_per_mps", 0.002))
        self.battery_capacity_j = float(cfg.get("battery_capacity_j", 0.0))
        self.electrical_efficiency = max(1e-6, float(cfg.get("electrical_efficiency", 0.72)))
        self.table: Table1D | None = None
        if "thrust_curve" in cfg:
            self.table = Table1D.from_pairs(cfg["thrust_curve"])

    def sample(self, t: float, throttle: float, mass_kg: float, dry_mass_kg: float, dt: float | None = None, airspeed_mps: float = 0.0) -> PropulsionSample:
        if t < self.ignition_delay_s:
            return PropulsionSample(np.zeros(3), np.zeros(3), 0.0, 0.0, float(throttle), 0.0, "ignition_delay")
        if self._shutdown_active(t):
            if not self.restart_allowed:
                self.actual_throttle = 0.0
            return PropulsionSample(np.zeros(3), np.zeros(3), 0.0, 0.0, float(throttle), self.actual_throttle, "shutdown")
        if t > self.burn_time_s or mass_kg <= dry_mass_kg:
            self.actual_throttle = 0.0
            return PropulsionSample(np.zeros(3), np.zeros(3), 0.0, 0.0, float(throttle), 0.0, "burnout")
        cmd = max(0.0, min(1.0, float(throttle)))
        if self.throttleable and cmd > 0.0:
            cmd = max(self.min_throttle, cmd)
        elif not self.throttleable:
            cmd = 1.0 if cmd > 0.0 else 0.0
        self.actual_throttle = self._lagged_throttle(cmd, dt)
        base = self._base_thrust(t, airspeed_mps)
        thrust_n = max(0.0, base * self.actual_throttle)
        pitch_cant, yaw_cant, _ = self.misalignment_rad
        direction = np.array([1.0, yaw_cant, pitch_cant], dtype=float)
        direction /= max(float(np.linalg.norm(direction)), 1e-12)
        force = direction * thrust_n
        moment = np.cross(self.position_body_m, force) + self.nozzle_cant_moment_nm * cmd
        mass_flow = self._mass_flow(thrust_n, airspeed_mps)
        return PropulsionSample(force, moment, mass_flow, thrust_n, cmd, self.actual_throttle, "nominal" if thrust_n > 0.0 else "off")

    def _base_thrust(self, t: float, airspeed_mps: float) -> float:
        if self.model == "electric":
            return max(0.0, self.electric_static_thrust_n * (1.0 - self.electric_speed_loss * max(0.0, airspeed_mps)))
        return self.table(t) if self.table is not None else self.max_thrust_n

    def _mass_flow(self, thrust_n: float, airspeed_mps: float) -> float:
        if self.model == "electric":
            if self.battery_capacity_j <= 0.0:
                return 0.0
            mechanical_power = thrust_n * max(1.0, airspeed_mps)
            return mechanical_power / self.electrical_efficiency / max(self.battery_capacity_j, 1e-9)
        return thrust_n / max(self.isp_s * G0, 1e-9)

    def _lagged_throttle(self, cmd: float, dt: float | None) -> float:
        if self.engine_lag_s <= 1e-9 or dt is None:
            if self.engine_lag_s <= 1e-9:
                self.actual_throttle = cmd
        else:
            alpha = max(0.0, min(1.0, dt / self.engine_lag_s))
            self.actual_throttle += alpha * (cmd - self.actual_throttle)
        return self.actual_throttle

    def _shutdown_active(self, t: float) -> bool:
        return any(start <= t <= end for start, end in self.shutdown_intervals)
