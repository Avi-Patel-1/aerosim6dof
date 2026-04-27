"""Sensor log analysis and report generation."""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any

import numpy as np

from aerosim6dof.reports.csv_writer import read_csv, write_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.svg import write_time_plot


def sensor_report(run_dir: str | Path, out_dir: str | Path | None = None) -> dict[str, Any]:
    """Build sensor error metrics and a static HTML report from a run directory."""

    run = Path(run_dir)
    history_path = run / "history.csv"
    if not history_path.exists():
        raise ValueError(f"{history_path} does not exist")
    rows = read_csv(history_path)
    if not rows:
        raise ValueError(f"{history_path} has no rows")
    out = Path(out_dir) if out_dir is not None else run / "sensor_report"
    out.mkdir(parents=True, exist_ok=True)
    metrics = _metrics(rows)
    write_json(out / "sensor_metrics.json", metrics)
    write_csv(out / "sensor_metrics.csv", _metric_rows(metrics))
    plots = _plots(out, rows)
    report_path = _write_html(out, metrics, plots)
    metrics["report"] = str(report_path)
    return metrics


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    gps_rows = _valid_rows(rows, "gps_valid", ["gps_x_m", "gps_y_m", "gps_z_m"])
    gps_vel_rows = _valid_rows(rows, "gps_valid", ["gps_vx_mps", "gps_vy_mps", "gps_vz_mps"])
    metrics: dict[str, Any] = {
        "samples": len(rows),
        "gps_valid_fraction": _valid_fraction(rows, "gps_valid"),
        "barometer_valid_fraction": _valid_fraction(rows, "baro_valid"),
        "pitot_valid_fraction": _valid_fraction(rows, "pitot_valid"),
        "magnetometer_valid_fraction": _valid_fraction(rows, "mag_valid"),
        "radar_valid_fraction": _valid_fraction(rows, "radar_valid"),
        "optical_flow_valid_fraction": _valid_fraction(rows, "optical_flow_valid"),
        "horizon_valid_fraction": _valid_fraction(rows, "horizon_valid"),
        "imu_accel_norm_mean_mps2": _mean([r.get("imu_accel_norm_mps2") for r in rows]),
        "imu_gyro_norm_mean_rps": _mean([r.get("imu_gyro_norm_rps") for r in rows]),
    }
    metrics["gps_position_rmse_m"] = _vector_rmse(
        gps_rows,
        ("gps_x_m", "gps_y_m", "gps_z_m"),
        ("x_m", "y_m", "altitude_m"),
    )
    metrics["gps_velocity_rmse_mps"] = _vector_rmse(
        gps_vel_rows,
        ("gps_vx_mps", "gps_vy_mps", "gps_vz_mps"),
        ("vx_mps", "vy_mps", "vz_mps"),
    )
    metrics["barometer_altitude_rmse_m"] = _scalar_rmse(_valid_rows(rows, "baro_valid", ["baro_alt_m"]), "baro_alt_m", "altitude_m")
    metrics["pitot_airspeed_rmse_mps"] = _scalar_rmse(
        _valid_rows(rows, "pitot_valid", ["pitot_airspeed_mps"]),
        "pitot_airspeed_mps",
        "airspeed_mps",
    )
    metrics["radar_agl_rmse_m_flat_terrain"] = _scalar_rmse(
        _valid_rows(rows, "radar_valid", ["radar_agl_m"]),
        "radar_agl_m",
        "altitude_m",
    )
    metrics["magnetometer_heading_rmse_deg"] = _angle_rmse(_valid_rows(rows, "mag_valid", ["mag_heading_deg"]), "mag_heading_deg", "yaw_deg")
    metrics["horizon_roll_rmse_deg"] = _scalar_rmse(_valid_rows(rows, "horizon_valid", ["horizon_roll_deg"]), "horizon_roll_deg", "roll_deg")
    metrics["horizon_pitch_rmse_deg"] = _scalar_rmse(_valid_rows(rows, "horizon_valid", ["horizon_pitch_deg"]), "horizon_pitch_deg", "pitch_deg")
    metrics["sensor_dropout_events"] = _dropout_events(rows)
    return metrics


def _plots(out: Path, rows: list[dict[str, Any]]) -> list[Path]:
    plot_dir = out / "plots"
    specs = [
        ("gps_altitude_error.svg", ["altitude_m", "gps_z_m"], "GPS Altitude", "altitude (m)"),
        ("barometer_altitude_error.svg", ["altitude_m", "baro_alt_m"], "Barometer Altitude", "altitude (m)"),
        ("pitot_airspeed_error.svg", ["airspeed_mps", "pitot_airspeed_mps"], "Pitot Airspeed", "airspeed (m/s)"),
        ("magnetometer_heading_error.svg", ["yaw_deg", "mag_heading_deg"], "Magnetometer Heading", "heading (deg)"),
        ("radar_altimeter.svg", ["altitude_m", "radar_agl_m"], "Radar Altimeter", "height (m)"),
        ("horizon_pitch.svg", ["pitch_deg", "horizon_pitch_deg"], "Horizon Pitch", "pitch (deg)"),
        ("imu_norms.svg", ["imu_accel_norm_mps2", "imu_gyro_norm_rps"], "IMU Norms", "norm"),
    ]
    paths: list[Path] = []
    for filename, keys, title, label in specs:
        path = plot_dir / filename
        write_time_plot(path, rows, keys, title, label)
        paths.append(path)
    return paths


def _write_html(out: Path, metrics: dict[str, Any], plots: list[Path]) -> Path:
    rows = "\n".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(_fmt(v))}</td></tr>"
        for k, v in metrics.items()
        if k != "sensor_dropout_events"
    )
    dropouts = metrics.get("sensor_dropout_events", {})
    dropout_rows = "\n".join(
        f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>" for k, v in sorted(dropouts.items())
    ) or "<tr><td colspan=\"2\">No valid-flag transitions recorded.</td></tr>"
    plot_html = "\n".join(
        f'<figure><img src="{html.escape(str(p.relative_to(out)))}" alt="{html.escape(p.stem)}"><figcaption>{html.escape(p.stem.replace("_", " "))}</figcaption></figure>'
        for p in plots
    )
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Sensor Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; background: #f7f8fa; }}
    main {{ max-width: 1120px; margin: 0 auto; }}
    table {{ border-collapse: collapse; background: white; margin: 18px 0; min-width: 460px; }}
    th, td {{ border: 1px solid #d9dee7; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef2f7; }}
    figure {{ background: white; border: 1px solid #d9dee7; margin: 18px 0; padding: 12px; }}
    img {{ width: 100%; height: auto; display: block; }}
    figcaption {{ font-size: 12px; color: #52616f; margin-top: 8px; }}
  </style>
</head>
<body>
<main>
  <h1>Sensor Report</h1>
  <p>Sensor measurements compared against simulator truth channels.</p>
  <h2>Error Metrics</h2>
  <table>{rows}</table>
  <h2>Valid-Flag Transitions</h2>
  <table><tr><th>Sensor</th><th>Transitions</th></tr>{dropout_rows}</table>
  <h2>Plots</h2>
  {plot_html}
</main>
</body>
</html>
"""
    path = out / "sensor_report.html"
    path.write_text(doc)
    return path


def _valid_fraction(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [_finite_or_none(r.get(key)) for r in rows if key in r]
    if not values:
        return None
    return float(sum(1 for value in values if value is not None and value > 0.5) / len(values))


def _valid_rows(rows: list[dict[str, Any]], valid_key: str, keys: list[str]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if _finite_or_none(row.get(valid_key)) is not None
        and float(row.get(valid_key, 0.0)) > 0.5
        and all(_finite_or_none(row.get(key)) is not None for key in keys)
    ]


def _vector_rmse(rows: list[dict[str, Any]], measured_keys: tuple[str, ...], truth_keys: tuple[str, ...]) -> float | None:
    errors = []
    for row in rows:
        measured = np.array([float(row[k]) for k in measured_keys], dtype=float)
        truth = np.array([float(row[k]) for k in truth_keys], dtype=float)
        errors.append(float(np.linalg.norm(measured - truth)))
    return _rmse(errors)


def _scalar_rmse(rows: list[dict[str, Any]], measured_key: str, truth_key: str) -> float | None:
    errors = []
    for row in rows:
        measured = _finite_or_none(row.get(measured_key))
        truth = _finite_or_none(row.get(truth_key))
        if measured is not None and truth is not None:
            errors.append(measured - truth)
    return _rmse(errors)


def _angle_rmse(rows: list[dict[str, Any]], measured_key: str, truth_key: str) -> float | None:
    errors = []
    for row in rows:
        measured = _finite_or_none(row.get(measured_key))
        truth = _finite_or_none(row.get(truth_key))
        if measured is not None and truth is not None:
            diff = (measured - truth + 180.0) % 360.0 - 180.0
            errors.append(diff)
    return _rmse(errors)


def _dropout_events(rows: list[dict[str, Any]]) -> dict[str, int]:
    keys = ["gps_valid", "baro_valid", "pitot_valid", "mag_valid", "radar_valid", "optical_flow_valid", "horizon_valid", "imu_valid"]
    events: dict[str, int] = {}
    for key in keys:
        previous: bool | None = None
        count = 0
        for row in rows:
            value = _finite_or_none(row.get(key))
            if value is None:
                continue
            valid = value > 0.5
            if previous is not None and valid != previous:
                count += 1
            previous = valid
        if previous is not None:
            events[key] = count
    return events


def _metric_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"metric": key, "value": _fmt(value)} for key, value in metrics.items() if key != "sensor_dropout_events"]


def _mean(values: list[Any]) -> float | None:
    finite = [float(v) for v in values if _finite_or_none(v) is not None]
    return float(np.mean(finite)) if finite else None


def _rmse(errors: list[float]) -> float | None:
    if not errors:
        return None
    arr = np.asarray(errors, dtype=float)
    return float(np.sqrt(np.mean(arr * arr)))


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if value is None:
        return "-"
    return str(value)
