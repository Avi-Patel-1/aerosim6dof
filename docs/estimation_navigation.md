# Estimation Navigation

`aerosim6dof.estimation` provides a standalone navigation layer for offline
truth-vs-sensor-vs-estimate studies. It does not modify the simulator runner,
logger, or sensor models.

## Constant-Velocity Filter

`ConstantVelocityNavigationFilter` is a lightweight NumPy Kalman filter with a
six-state vector:

```text
[x_m, y_m, z_m, vx_mps, vy_mps, vz_mps]
```

The prediction model assumes constant velocity and adds configurable white
acceleration process noise. GNSS updates can use any finite subset of
`gps_x_m`, `gps_y_m`, `gps_z_m`, `gps_vx_mps`, `gps_vy_mps`, and `gps_vz_mps`.
Missing or non-numeric channels are ignored instead of raising.

## Telemetry Helper

Use `build_navigation_telemetry(sensor_rows, truth_rows=None, config=None)` to
run the filter over row dictionaries from `sensors.csv`, `truth.csv`, or
combined `history.csv` data.

When `truth_rows` is omitted, the helper reads truth fields from the same row.
This supports `history.csv` rows directly. When separate rows are supplied, rows
are paired by order.

Each output row includes:

- estimated position and velocity
- covariance diagonal, covariance trace, position sigma, and velocity sigma
- GNSS quality score, whether a GNSS update was used, and update dimension
- truth position/velocity when available
- estimate error norms and component errors when truth is available
- GNSS measurement error norms when both GNSS and truth are available

## GNSS Quality Score

`gnss_quality_score(row, config=None)` returns a value in `[0, 1]`.

The score is zero when `gps_valid` is false or a dropout-active field is set.
Otherwise it is degraded by recognized dropout probability, noise, and latency
fields:

- `gps_dropout_probability`, `gnss_dropout_probability`, `dropout_probability`
- `gps_position_noise_std_m`, `position_noise_std_m`, `gps_noise_std_m`
- `gps_velocity_noise_std_mps`, `velocity_noise_std_mps`
- `gps_latency_s`, `gnss_latency_s`, `latency_s`

The same keys can be supplied in `config` as defaults for rows that do not carry
sensor configuration metadata. A nested `config["gps"]` or `config["gnss"]`
dictionary is also recognized.

## Example

```python
from aerosim6dof.estimation import build_navigation_telemetry

telemetry = build_navigation_telemetry(
    sensor_rows,
    truth_rows,
    config={
        "process_noise_accel_mps2": 0.5,
        "gnss_position_noise_m": 3.0,
        "gnss_velocity_noise_mps": 0.3,
    },
)
```

The helper returns plain dictionaries so callers can write CSV/JSON artifacts or
feed the rows into the existing reporting stack later.
