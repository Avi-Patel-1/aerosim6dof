"""GPS sensor model."""

from __future__ import annotations

from typing import Any

import numpy as np

from aerosim6dof.core.vectors import vec3


class GPSSensor:
    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.pos_noise = float(cfg.get("position_noise_std_m", cfg.get("gps_noise_std_m", 1.5)))
        self.vel_noise = float(cfg.get("velocity_noise_std_mps", 0.15))
        self.dropout_probability = float(cfg.get("dropout_probability", 0.0))
        self.bias = vec3(cfg.get("position_bias_m"), (0.0, 0.0, 0.0))
        self.velocity_bias = vec3(cfg.get("velocity_bias_mps"), (0.0, 0.0, 0.0))
        self.latency_s = max(0.0, float(cfg.get("latency_s", 0.0)))
        self.multipath_amplitude_m = float(cfg.get("multipath_amplitude_m", 0.0))
        self.multipath_period_s = max(1e-6, float(cfg.get("multipath_period_s", 17.0)))
        self.multipath_axis = vec3(cfg.get("multipath_axis"), (0.7, -0.3, 0.2))
        norm = float(np.linalg.norm(self.multipath_axis))
        if norm > 0.0:
            self.multipath_axis = self.multipath_axis / norm
        self._buffer: list[tuple[float, np.ndarray, np.ndarray]] = []

    def sample(
        self,
        rng: np.random.Generator,
        position_m: np.ndarray,
        velocity_mps: np.ndarray,
        t: float,
        extra_position_bias_m: np.ndarray | None = None,
        dropout: bool = False,
    ) -> dict[str, float]:
        delayed_position, delayed_velocity = self._delayed_truth(float(t), position_m, velocity_mps)
        if dropout or rng.random() < self.dropout_probability:
            return {"gps_valid": 0.0, "gps_latency_s": float(self.latency_s)}
        multipath = self.multipath_axis * self.multipath_amplitude_m * np.sin(2.0 * np.pi * t / self.multipath_period_s)
        pos_bias = self.bias + multipath + (extra_position_bias_m if extra_position_bias_m is not None else 0.0)
        pos = delayed_position + pos_bias + rng.normal(0.0, self.pos_noise, 3)
        vel = delayed_velocity + self.velocity_bias + rng.normal(0.0, self.vel_noise, 3)
        return {
            "gps_valid": 1.0,
            "gps_latency_s": float(self.latency_s),
            "gps_x_m": float(pos[0]),
            "gps_y_m": float(pos[1]),
            "gps_z_m": float(pos[2]),
            "gps_vx_mps": float(vel[0]),
            "gps_vy_mps": float(vel[1]),
            "gps_vz_mps": float(vel[2]),
        }

    def _delayed_truth(self, t: float, position_m: np.ndarray, velocity_mps: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        self._buffer.append((t, position_m.copy(), velocity_mps.copy()))
        cutoff = t - max(self.latency_s, 0.0)
        while len(self._buffer) > 2 and self._buffer[1][0] <= cutoff:
            self._buffer.pop(0)
        for sample_t, sample_pos, sample_vel in reversed(self._buffer):
            if sample_t <= cutoff:
                return sample_pos.copy(), sample_vel.copy()
        return self._buffer[0][1].copy(), self._buffer[0][2].copy()
