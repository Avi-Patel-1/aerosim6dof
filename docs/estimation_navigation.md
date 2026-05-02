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
- API-stable aliases: `estimate_altitude_m`, `estimate_speed_mps`,
  `estimate_position_error_m`, `estimate_velocity_error_mps`, `gnss_quality`,
  and `gps_valid`
- covariance diagonal, covariance trace, position sigma, and velocity sigma
- GNSS quality score, whether a GNSS update was used, and update dimension
- truth position/velocity when available
- estimate error norms and component errors when truth is available
- GNSS measurement error norms when both GNSS and truth are available

The legacy keys `position_error_m`, `velocity_error_mps`, and
`gnss_quality_score` remain present for existing analysis code. The API aliases
are always included, with `None` when the source rows do not contain enough
truth or sensor data to compute them.

## Run Directory Loader

Use `load_navigation_telemetry_from_run(run_dir, stride=1)` when wiring a web
API to a completed simulation run directory. The loader uses the existing CSV
reader and returns:

```python
{
    "rows": [...],
    "channels": [...],
    "summary": {...},
}
```

The loader prefers `sensors.csv` paired with `truth.csv`. If `sensors.csv` is
missing or empty, it falls back to combined `history.csv` rows. Missing optional
files, unknown sensor columns, non-numeric values, and sparse GNSS channels do
not crash the loader; unavailable values are left as `None` and the summary
includes warnings for missing or unreadable run inputs.

The returned rows are flat dictionaries intended for direct JSON serialization
and frontend telemetry tables. Core channel metadata is included for:

- `time_s`
- `estimate_x_m`, `estimate_y_m`, `estimate_z_m`
- `estimate_vx_mps`, `estimate_vy_mps`, `estimate_vz_mps`
- `estimate_altitude_m`, `estimate_speed_mps`
- `estimate_position_error_m`, `estimate_velocity_error_mps`
- `gnss_quality`, `covariance_trace`, `gps_valid`

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
from aerosim6dof.estimation.navigation_filter import load_navigation_telemetry_from_run

telemetry = build_navigation_telemetry(
    sensor_rows,
    truth_rows,
    config={
        "process_noise_accel_mps2": 0.5,
        "gnss_position_noise_m": 3.0,
        "gnss_velocity_noise_mps": 0.3,
    },
)

payload = load_navigation_telemetry_from_run("outputs/web_runs/seed_scenario_suite/nominal_ascent", stride=10)
```

The helper returns plain dictionaries so callers can write CSV/JSON artifacts or
feed the rows into the existing reporting stack later.
