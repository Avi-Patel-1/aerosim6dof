"""Standalone navigation estimation helpers.

The module intentionally accepts plain dictionaries so it can be used with
`truth.csv`, `sensors.csv`, or combined `history.csv` rows without coupling the
simulator runner or logger to an estimator implementation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np


POSITION_KEYS = ("x_m", "y_m", "altitude_m")
VELOCITY_KEYS = ("vx_mps", "vy_mps", "vz_mps")
GPS_POSITION_KEYS = ("gps_x_m", "gps_y_m", "gps_z_m")
GPS_VELOCITY_KEYS = ("gps_vx_mps", "gps_vy_mps", "gps_vz_mps")


@dataclass(frozen=True)
class NavigationEstimate:
    """Snapshot of the constant-velocity navigation state."""

    time_s: float | None
    position_m: np.ndarray
    velocity_mps: np.ndarray
    covariance: np.ndarray
    gnss_quality_score: float
    gnss_used: bool
    update_dimension: int


class ConstantVelocityNavigationFilter:
    """Small NumPy constant-velocity Kalman filter for navigation studies."""

    def __init__(
        self,
        *,
        initial_state: Iterable[float] | None = None,
        initial_covariance: Iterable[Iterable[float]] | None = None,
        process_noise_accel_mps2: float = 1.0,
        gnss_position_noise_m: float = 5.0,
        gnss_velocity_noise_mps: float = 0.75,
        max_dt_s: float = 5.0,
    ):
        self.process_noise_accel_mps2 = max(0.0, _finite_or_default(process_noise_accel_mps2, 1.0))
        self.gnss_position_noise_m = max(1e-6, _finite_or_default(gnss_position_noise_m, 5.0))
        self.gnss_velocity_noise_mps = max(1e-6, _finite_or_default(gnss_velocity_noise_mps, 0.75))
        self.max_dt_s = max(1e-6, _finite_or_default(max_dt_s, 5.0))
        self.state = np.zeros(6, dtype=float)
        if initial_state is not None:
            try:
                candidate = np.asarray(list(initial_state), dtype=float)
            except (TypeError, ValueError):
                candidate = np.asarray([], dtype=float)
            if candidate.shape != (6,) or not np.all(np.isfinite(candidate)):
                raise ValueError("initial_state must contain six finite values")
            self.state = candidate.copy()
            self.initialized = True
        else:
            self.initialized = False
        self.covariance = _coerce_covariance(initial_covariance)
        self.time_s: float | None = None
        self.last_gnss_quality_score = 0.0
        self.last_gnss_used = False
        self.last_update_dimension = 0

    def initialize(
        self,
        *,
        position_m: Iterable[float],
        velocity_mps: Iterable[float] | None = None,
        time_s: float | None = None,
        covariance: Iterable[Iterable[float]] | None = None,
    ) -> NavigationEstimate:
        """Initialize the state from a position and optional velocity."""

        position = _coerce_vector(position_m)
        velocity = _coerce_vector(velocity_mps, default=(0.0, 0.0, 0.0))
        if position is None or velocity is None:
            raise ValueError("position_m and velocity_mps must contain finite numeric values")
        self.state = np.concatenate((position, velocity)).astype(float)
        if covariance is not None:
            self.covariance = _coerce_covariance(covariance)
        self.initialized = True
        self.time_s = _finite_or_none(time_s)
        self.last_gnss_quality_score = 1.0
        self.last_gnss_used = False
        self.last_update_dimension = 0
        return self.estimate()

    def predict(self, dt_s: float | None) -> NavigationEstimate:
        """Advance the filter with a constant-velocity process model."""

        dt = _finite_or_none(dt_s)
        if dt is None or dt <= 0.0:
            return self.estimate()
        dt = min(dt, self.max_dt_s)
        transition = np.eye(6)
        transition[0:3, 3:6] = np.eye(3) * dt
        q = self.process_noise_accel_mps2 * self.process_noise_accel_mps2
        process = np.zeros((6, 6), dtype=float)
        process[0:3, 0:3] = np.eye(3) * (0.25 * dt**4 * q)
        process[0:3, 3:6] = np.eye(3) * (0.5 * dt**3 * q)
        process[3:6, 0:3] = np.eye(3) * (0.5 * dt**3 * q)
        process[3:6, 3:6] = np.eye(3) * (dt**2 * q)
        self.state = transition @ self.state
        self.covariance = transition @ self.covariance @ transition.T + process
        self.covariance = _symmetrize_covariance(self.covariance)
        if self.time_s is not None:
            self.time_s += dt
        self.last_gnss_used = False
        self.last_update_dimension = 0
        return self.estimate()

    def update_gnss(self, sensor_row: dict[str, Any], *, config: dict[str, Any] | None = None) -> NavigationEstimate:
        """Apply any finite GNSS position and velocity channels in a row."""

        quality = gnss_quality_score(sensor_row, config=config)
        if not self.initialized:
            if quality > 0.0:
                self._initialize_from_row(sensor_row)
            else:
                self.initialized = True
        self.last_gnss_quality_score = quality
        self.last_gnss_used = False
        self.last_update_dimension = 0
        if quality <= 0.0:
            return self.estimate()

        measurements: list[float] = []
        rows: list[np.ndarray] = []
        variances: list[float] = []
        position_noise_m = _noise_value(
            sensor_row,
            config,
            (
                "gps_position_noise_std_m",
                "position_noise_std_m",
                "gps_noise_std_m",
                "gnss_position_noise_std_m",
                "gnss_position_noise_m",
            ),
            self.gnss_position_noise_m,
        )
        velocity_noise_mps = _noise_value(
            sensor_row,
            config,
            ("gps_velocity_noise_std_mps", "velocity_noise_std_mps", "gnss_velocity_noise_std_mps", "gnss_velocity_noise_mps"),
            self.gnss_velocity_noise_mps,
        )
        variance_scale = 1.0 / max(quality, 0.05)
        for index, key in enumerate(GPS_POSITION_KEYS):
            value = _finite_or_none(sensor_row.get(key))
            if value is None:
                continue
            h_row = np.zeros(6, dtype=float)
            h_row[index] = 1.0
            measurements.append(value)
            rows.append(h_row)
            variances.append(position_noise_m * position_noise_m * variance_scale)
        for index, key in enumerate(GPS_VELOCITY_KEYS, start=3):
            value = _finite_or_none(sensor_row.get(key))
            if value is None:
                continue
            h_row = np.zeros(6, dtype=float)
            h_row[index] = 1.0
            measurements.append(value)
            rows.append(h_row)
            variances.append(velocity_noise_mps * velocity_noise_mps * variance_scale)
        if not measurements:
            return self.estimate()

        z = np.asarray(measurements, dtype=float)
        h = np.vstack(rows)
        r = np.diag(np.asarray(variances, dtype=float))
        innovation = z - h @ self.state
        innovation_cov = h @ self.covariance @ h.T + r
        try:
            gain = np.linalg.solve(innovation_cov.T, (self.covariance @ h.T).T).T
        except np.linalg.LinAlgError:
            gain = self.covariance @ h.T @ np.linalg.pinv(innovation_cov)
        self.state = self.state + gain @ innovation
        identity = np.eye(6)
        joseph = identity - gain @ h
        self.covariance = joseph @ self.covariance @ joseph.T + gain @ r @ gain.T
        self.covariance = _symmetrize_covariance(self.covariance)
        self.last_gnss_used = True
        self.last_update_dimension = len(measurements)
        return self.estimate()

    def step(
        self,
        sensor_row: dict[str, Any],
        *,
        truth_row: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> NavigationEstimate:
        """Predict to row time and apply a GNSS update when available."""

        row_time = _row_time(sensor_row, truth_row)
        if self.time_s is None:
            self.time_s = row_time
        elif row_time is not None:
            self.predict(row_time - self.time_s)
            self.time_s = row_time
        return self.update_gnss(sensor_row, config=config)

    def estimate(self) -> NavigationEstimate:
        """Return the current estimate as copied arrays."""

        return NavigationEstimate(
            time_s=self.time_s,
            position_m=self.state[0:3].copy(),
            velocity_mps=self.state[3:6].copy(),
            covariance=self.covariance.copy(),
            gnss_quality_score=float(self.last_gnss_quality_score),
            gnss_used=bool(self.last_gnss_used),
            update_dimension=int(self.last_update_dimension),
        )

    def telemetry_row(
        self,
        *,
        sensor_row: dict[str, Any] | None = None,
        truth_row: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a telemetry row with estimate, covariance, and errors."""

        return navigation_telemetry_row(self.estimate(), sensor_row=sensor_row, truth_row=truth_row)

    def _initialize_from_row(self, sensor_row: dict[str, Any]) -> None:
        position = _vector_from_row(sensor_row, GPS_POSITION_KEYS)
        velocity = _vector_from_row(sensor_row, GPS_VELOCITY_KEYS, default=(0.0, 0.0, 0.0))
        if position is None:
            self.initialized = True
            return
        if velocity is None:
            velocity = np.zeros(3, dtype=float)
        self.state = np.concatenate((position, velocity)).astype(float)
        self.initialized = True


def build_navigation_telemetry(
    sensor_rows: Iterable[dict[str, Any]],
    truth_rows: Iterable[dict[str, Any]] | None = None,
    *,
    config: dict[str, Any] | None = None,
    initial_state: Iterable[float] | None = None,
) -> list[dict[str, Any]]:
    """Run the navigation filter over rows and emit comparison telemetry.

    `truth_rows` is optional; when omitted, truth fields are read from each
    sensor row, which matches combined `history.csv` rows.
    """

    filter_config = dict(config or {})
    estimator = ConstantVelocityNavigationFilter(
        initial_state=initial_state,
        process_noise_accel_mps2=_finite_or_default(filter_config.get("process_noise_accel_mps2"), 1.0),
        gnss_position_noise_m=_finite_or_default(filter_config.get("gnss_position_noise_m"), 5.0),
        gnss_velocity_noise_mps=_finite_or_default(filter_config.get("gnss_velocity_noise_mps"), 0.75),
        max_dt_s=_finite_or_default(filter_config.get("max_dt_s"), 5.0),
    )
    truth_iter = iter(truth_rows) if truth_rows is not None else None
    output: list[dict[str, Any]] = []
    for sensor_row in sensor_rows:
        truth_row = next(truth_iter, None) if truth_iter is not None else sensor_row
        estimate = estimator.step(sensor_row, truth_row=truth_row, config=filter_config)
        output.append(navigation_telemetry_row(estimate, sensor_row=sensor_row, truth_row=truth_row))
    return output


def navigation_telemetry_row(
    estimate: NavigationEstimate,
    *,
    sensor_row: dict[str, Any] | None = None,
    truth_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a flat row for CSV/JSON reporting of estimate quality."""

    row: dict[str, Any] = {
        "time_s": estimate.time_s,
        "estimate_x_m": float(estimate.position_m[0]),
        "estimate_y_m": float(estimate.position_m[1]),
        "estimate_z_m": float(estimate.position_m[2]),
        "estimate_vx_mps": float(estimate.velocity_mps[0]),
        "estimate_vy_mps": float(estimate.velocity_mps[1]),
        "estimate_vz_mps": float(estimate.velocity_mps[2]),
        "cov_x_m2": float(max(0.0, estimate.covariance[0, 0])),
        "cov_y_m2": float(max(0.0, estimate.covariance[1, 1])),
        "cov_z_m2": float(max(0.0, estimate.covariance[2, 2])),
        "cov_vx_m2ps2": float(max(0.0, estimate.covariance[3, 3])),
        "cov_vy_m2ps2": float(max(0.0, estimate.covariance[4, 4])),
        "cov_vz_m2ps2": float(max(0.0, estimate.covariance[5, 5])),
        "position_sigma_m": float(math.sqrt(max(0.0, np.trace(estimate.covariance[0:3, 0:3])))),
        "velocity_sigma_mps": float(math.sqrt(max(0.0, np.trace(estimate.covariance[3:6, 3:6])))),
        "covariance_trace": float(max(0.0, np.trace(estimate.covariance))),
        "gnss_quality_score": float(estimate.gnss_quality_score),
        "gnss_used": 1.0 if estimate.gnss_used else 0.0,
        "update_dimension": float(estimate.update_dimension),
    }
    truth_position = _truth_position(truth_row or {})
    truth_velocity = _vector_from_row(truth_row or {}, VELOCITY_KEYS)
    sensor_position = _vector_from_row(sensor_row or {}, GPS_POSITION_KEYS)
    sensor_velocity = _vector_from_row(sensor_row or {}, GPS_VELOCITY_KEYS)
    if truth_position is not None:
        row.update(
            {
                "truth_x_m": float(truth_position[0]),
                "truth_y_m": float(truth_position[1]),
                "truth_z_m": float(truth_position[2]),
                "x_error_m": float(estimate.position_m[0] - truth_position[0]),
                "y_error_m": float(estimate.position_m[1] - truth_position[1]),
                "z_error_m": float(estimate.position_m[2] - truth_position[2]),
                "position_error_m": float(np.linalg.norm(estimate.position_m - truth_position)),
            }
        )
    if truth_velocity is not None:
        row.update(
            {
                "truth_vx_mps": float(truth_velocity[0]),
                "truth_vy_mps": float(truth_velocity[1]),
                "truth_vz_mps": float(truth_velocity[2]),
                "vx_error_mps": float(estimate.velocity_mps[0] - truth_velocity[0]),
                "vy_error_mps": float(estimate.velocity_mps[1] - truth_velocity[1]),
                "vz_error_mps": float(estimate.velocity_mps[2] - truth_velocity[2]),
                "velocity_error_mps": float(np.linalg.norm(estimate.velocity_mps - truth_velocity)),
            }
        )
    if sensor_position is not None:
        row.update(
            {
                "sensor_gps_x_m": float(sensor_position[0]),
                "sensor_gps_y_m": float(sensor_position[1]),
                "sensor_gps_z_m": float(sensor_position[2]),
            }
        )
        if truth_position is not None:
            row["gps_position_error_m"] = float(np.linalg.norm(sensor_position - truth_position))
    if sensor_velocity is not None:
        row.update(
            {
                "sensor_gps_vx_mps": float(sensor_velocity[0]),
                "sensor_gps_vy_mps": float(sensor_velocity[1]),
                "sensor_gps_vz_mps": float(sensor_velocity[2]),
            }
        )
        if truth_velocity is not None:
            row["gps_velocity_error_mps"] = float(np.linalg.norm(sensor_velocity - truth_velocity))
    return row


def gnss_quality_score(row: dict[str, Any], *, config: dict[str, Any] | None = None) -> float:
    """Score GNSS usability from validity, dropout, latency, and noise fields."""

    valid = _finite_or_none(row.get("gps_valid"))
    if "gps_valid" in row and valid is None:
        return 0.0
    if valid is not None and valid <= 0.5:
        return 0.0
    dropout_active = _first_finite(row, config, ("gps_dropout", "gps_dropout_active", "gnss_dropout", "dropout"))
    if dropout_active is not None and dropout_active > 0.5:
        return 0.0
    if valid is None and not any(_finite_or_none(row.get(key)) is not None for key in GPS_POSITION_KEYS + GPS_VELOCITY_KEYS):
        return 0.0

    dropout_probability = _first_finite(
        row,
        config,
        ("gps_dropout_probability", "gnss_dropout_probability", "dropout_probability"),
    )
    position_noise = _first_finite(
        row,
        config,
        (
            "gps_position_noise_std_m",
            "position_noise_std_m",
            "gps_noise_std_m",
            "gnss_position_noise_std_m",
            "gnss_position_noise_m",
        ),
    )
    velocity_noise = _first_finite(
        row,
        config,
        ("gps_velocity_noise_std_mps", "velocity_noise_std_mps", "gnss_velocity_noise_std_mps", "gnss_velocity_noise_mps"),
    )
    latency = _first_finite(row, config, ("gps_latency_s", "gnss_latency_s", "latency_s"))
    score = 1.0
    if dropout_probability is not None:
        score *= 1.0 - _clip(dropout_probability, 0.0, 1.0)
    if position_noise is not None:
        score *= 5.0 / (5.0 + max(0.0, position_noise))
    if velocity_noise is not None:
        score *= 1.0 / (1.0 + max(0.0, velocity_noise))
    if latency is not None:
        score *= 1.0 / (1.0 + max(0.0, latency))
    return _clip(score, 0.0, 1.0)


def _coerce_covariance(value: Iterable[Iterable[float]] | None) -> np.ndarray:
    if value is None:
        covariance = np.diag([1.0e6, 1.0e6, 1.0e6, 1.0e4, 1.0e4, 1.0e4]).astype(float)
    else:
        covariance = np.asarray(value, dtype=float)
        if covariance.shape != (6, 6) or not np.all(np.isfinite(covariance)):
            raise ValueError("initial_covariance must be a finite 6x6 matrix")
    return _symmetrize_covariance(covariance)


def _symmetrize_covariance(covariance: np.ndarray) -> np.ndarray:
    symmetric = 0.5 * (covariance + covariance.T)
    diag = np.maximum(np.diag(symmetric), 1e-12)
    np.fill_diagonal(symmetric, diag)
    return symmetric


def _row_time(sensor_row: dict[str, Any], truth_row: dict[str, Any] | None) -> float | None:
    return _first_finite(sensor_row, truth_row, ("sensor_time_s", "time_s"))


def _truth_position(row: dict[str, Any]) -> np.ndarray | None:
    position = _vector_from_row(row, POSITION_KEYS)
    if position is not None:
        return position
    return _vector_from_row(row, ("x_m", "y_m", "z_m"))


def _vector_from_row(
    row: dict[str, Any],
    keys: tuple[str, str, str],
    *,
    default: Iterable[float] | None = None,
) -> np.ndarray | None:
    values = [_finite_or_none(row.get(key)) for key in keys]
    if all(value is not None for value in values):
        return np.asarray(values, dtype=float)
    if default is not None:
        return _coerce_vector(default)
    return None


def _coerce_vector(value: Iterable[float] | None, *, default: Iterable[float] | None = None) -> np.ndarray | None:
    if value is None:
        value = default
    if value is None:
        return None
    try:
        vector = np.asarray(list(value), dtype=float)
    except (TypeError, ValueError):
        return None
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        return None
    return vector


def _noise_value(
    row: dict[str, Any],
    config: dict[str, Any] | None,
    keys: tuple[str, ...],
    default: float,
) -> float:
    return max(1e-6, _finite_or_default(_first_finite(row, config, keys), default))


def _first_finite(
    primary: dict[str, Any] | None,
    secondary: dict[str, Any] | None,
    keys: tuple[str, ...],
) -> float | None:
    for source in _source_dicts(primary, secondary):
        for key in keys:
            value = _finite_or_none(source.get(key))
            if value is not None:
                return value
    return None


def _source_dicts(*sources: dict[str, Any] | None) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        expanded.append(source)
        for nested_key in ("gps", "gnss"):
            nested = source.get(nested_key)
            if isinstance(nested, dict):
                expanded.append(nested)
    return expanded


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite_or_default(value: Any, default: float) -> float:
    number = _finite_or_none(value)
    return float(default) if number is None else float(number)


def _clip(value: float, lower: float, upper: float) -> float:
    return float(min(upper, max(lower, value)))
