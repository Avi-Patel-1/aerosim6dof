"""Sensor suite with sample-rate handling."""

from __future__ import annotations

from typing import Any

import numpy as np

from aerosim6dof.core.quaternions import to_dcm
from aerosim6dof.core.vectors import vec3

from .barometer import BarometerSensor
from .gps import GPSSensor
from .horizon import HorizonSensor
from .imu import IMUSensor
from .magnetometer import MagnetometerSensor
from .optical_flow import OpticalFlowSensor
from .pitot import PitotSensor
from .radar_altimeter import RadarAltimeterSensor


class SensorSuite:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.rng = np.random.default_rng(int(self.config.get("seed", 7)))
        self.imu = IMUSensor({**self.config, **self.config.get("imu", {})})
        self.gps = GPSSensor({**self.config, **self.config.get("gps", {})})
        self.baro = BarometerSensor({**self.config, **self.config.get("barometer", {})})
        self.pitot = PitotSensor(self.config.get("pitot", {}))
        self.mag = MagnetometerSensor(self.config.get("magnetometer", {}))
        self.radar = RadarAltimeterSensor(self.config.get("radar_altimeter", {}))
        self.flow = OpticalFlowSensor(self.config.get("optical_flow", {}))
        self.horizon = HorizonSensor(self.config.get("horizon", {}))
        self.rates = {
            "imu": float(self.config.get("imu", {}).get("rate_hz", self.config.get("imu_rate_hz", 100.0))),
            "gps": float(self.config.get("gps", {}).get("rate_hz", self.config.get("gps_rate_hz", 5.0))),
            "barometer": float(self.config.get("barometer", {}).get("rate_hz", self.config.get("baro_rate_hz", 25.0))),
            "pitot": float(self.config.get("pitot", {}).get("rate_hz", 50.0)),
            "magnetometer": float(self.config.get("magnetometer", {}).get("rate_hz", 20.0)),
            "radar_altimeter": float(self.config.get("radar_altimeter", {}).get("rate_hz", 20.0)),
            "optical_flow": float(self.config.get("optical_flow", {}).get("rate_hz", 25.0)),
            "horizon": float(self.config.get("horizon", {}).get("rate_hz", 20.0)),
        }
        self.last_time = {name: -1e99 for name in self.rates}
        self.last_values: dict[str, float] = {}
        self.faults = [f for f in self.config.get("faults", []) if isinstance(f, dict)]

    def sample(self, t: float, dt: float, truth: dict[str, Any]) -> dict[str, float]:
        output = dict(self.last_values)
        output["sensor_time_s"] = float(t)
        agl_m = float(truth.get("altitude_agl_m", truth["position_m"][2]))
        velocity_body = to_dcm(truth["quaternion"]).T @ truth["velocity_mps"]
        if self._due("imu", t):
            fault = self._fault_state("imu", t)
            output.update(
                self.imu.sample(
                    self.rng,
                    truth["accel_body_mps2"],
                    truth["rates_rps"],
                    dt,
                    extra_accel_bias_mps2=vec3(fault.get("accel_bias_mps2"), (0.0, 0.0, 0.0)),
                    extra_gyro_bias_rps=vec3(fault.get("gyro_bias_rps"), (0.0, 0.0, 0.0)),
                    dropout=bool(fault.get("dropout", False)),
                )
            )
        if self._due("gps", t):
            fault = self._fault_state("gps", t)
            output.update(
                self.gps.sample(
                    self.rng,
                    truth["position_m"],
                    truth["velocity_mps"],
                    t,
                    extra_position_bias_m=vec3(fault.get("position_bias_m"), (0.0, 0.0, 0.0)),
                    dropout=bool(fault.get("dropout", False)),
                )
            )
        if self._due("barometer", t):
            fault = self._fault_state("barometer", t)
            output.update(
                self.baro.sample(
                    self.rng,
                    float(truth["position_m"][2]),
                    dt,
                    extra_bias_m=float(fault.get("bias_m", 0.0)),
                    dropout=bool(fault.get("dropout", False)),
                )
            )
        if self._due("pitot", t):
            fault = self._fault_state("pitot", t)
            output.update(
                self.pitot.sample(
                    self.rng,
                    float(truth["airspeed_mps"]),
                    float(truth["qbar_pa"]),
                    float(truth.get("mach", 0.0)),
                    extra_bias_mps=float(fault.get("bias_mps", 0.0)),
                    dropout=bool(fault.get("dropout", False)),
                )
            )
        if self._due("magnetometer", t):
            fault = self._fault_state("magnetometer", t)
            output.update(self.mag.sample(self.rng, truth["quaternion"], dropout=bool(fault.get("dropout", False))))
        if self._due("radar_altimeter", t):
            fault = self._fault_state("radar_altimeter", t)
            output.update(
                self.radar.sample(
                    self.rng,
                    agl_m,
                    extra_bias_m=float(fault.get("bias_m", 0.0)),
                    dropout=bool(fault.get("dropout", False)),
                )
            )
        if self._due("optical_flow", t):
            fault = self._fault_state("optical_flow", t)
            output.update(self.flow.sample(self.rng, velocity_body, agl_m, dropout=bool(fault.get("dropout", False))))
        if self._due("horizon", t):
            fault = self._fault_state("horizon", t)
            output.update(self.horizon.sample(self.rng, truth["quaternion"], dropout=bool(fault.get("dropout", False))))
        self.last_values = output
        return dict(output)

    def _due(self, name: str, t: float) -> bool:
        rate = max(0.0, self.rates.get(name, 0.0))
        if rate <= 0.0:
            return False
        period = 1.0 / rate
        if t - self.last_time[name] >= period - 1e-12:
            self.last_time[name] = t
            return True
        return False

    def _fault_state(self, sensor: str, t: float) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for fault in self.faults:
            target = fault.get("sensor", fault.get("target", fault.get("name", "")))
            targets = fault.get("sensors")
            target_names = {str(target)} if target else set()
            if isinstance(targets, list):
                target_names.update(str(item) for item in targets)
            if "*" not in target_names and sensor not in target_names:
                continue
            start = float(fault.get("start_s", 0.0))
            end = float(fault.get("end_s", 1e99))
            if not start <= t <= end:
                continue
            kind = str(fault.get("type", "bias_jump"))
            if kind == "dropout":
                state["dropout"] = True
            elif kind in {"bias_jump", "bias", "scale"}:
                for key, value in fault.items():
                    if key not in {"sensor", "sensors", "target", "name", "type", "start_s", "end_s"}:
                        state[key] = value
        return state
