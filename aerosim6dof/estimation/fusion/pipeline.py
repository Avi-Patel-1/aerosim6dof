"""Post-run estimation fusion report pipeline."""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any

from aerosim6dof.estimation.fusion.alignment import AlignedSample, align_run_tables, load_run_tables
from aerosim6dof.estimation.fusion.estimators import FusionEstimate, SimpleFusionEstimator
from aerosim6dof.estimation.fusion.metrics import metrics_by_name, summarize_numeric_rows
from aerosim6dof.estimation.fusion.quality import availability_summary
from aerosim6dof.reports.csv_writer import write_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.svg import write_time_plot


TRUTH_POSITION_KEYS = ("x_m", "y_m", "altitude_m")
TRUTH_VELOCITY_KEYS = ("vx_mps", "vy_mps", "vz_mps")
GPS_POSITION_KEYS = ("gps_x_m", "gps_y_m", "gps_z_m")
GPS_VELOCITY_KEYS = ("gps_vx_mps", "gps_vy_mps", "gps_vz_mps")
GYRO_KEYS = ("gyro_p_rps", "gyro_q_rps", "gyro_r_rps")
IMU_ACCEL_KEYS = ("imu_ax_mps2", "imu_ay_mps2", "imu_az_mps2")
TRUTH_ACCEL_KEY_SETS = (
    ("ax_mps2", "ay_mps2", "az_mps2"),
    ("body_ax_mps2", "body_ay_mps2", "body_az_mps2"),
)


def write_estimation_fusion_report(
    run_dir: str | Path,
    out_dir: str | Path | None = None,
    *,
    max_time_gap_s: float | None = None,
) -> dict[str, Any]:
    """Read a simulator run directory and write estimation fusion artifacts."""

    run_path = Path(run_dir)
    out = Path(out_dir) if out_dir is not None else run_path / "estimation_fusion"
    out.mkdir(parents=True, exist_ok=True)
    tables = load_run_tables(run_path)
    result = build_estimation_fusion(
        truth_rows=tables.truth,
        sensor_rows=tables.sensors,
        history_rows=tables.history,
        warnings=tables.warnings,
        source_files=tables.source_files,
        max_time_gap_s=max_time_gap_s,
    )
    residual_rows = result["residuals"]
    metric_rows = result["metric_rows"]
    write_csv(out / "residuals.csv", residual_rows)
    write_csv(out / "estimation_metrics.csv", metric_rows)
    plots = _write_plots(out, residual_rows)
    report_path = _write_html(out, result["summary"], metric_rows, plots)
    artifacts = {
        "summary_json": str(out / "estimation_summary.json"),
        "metrics_csv": str(out / "estimation_metrics.csv"),
        "residuals_csv": str(out / "residuals.csv"),
        "report_html": str(report_path),
        "plots": [str(path) for path in plots],
    }
    result["summary"]["artifacts"] = artifacts
    result["summary"]["run_dir"] = str(run_path)
    result["summary"]["output_dir"] = str(out)
    write_json(out / "estimation_summary.json", result["summary"])
    return result["summary"]


def build_estimation_fusion(
    *,
    truth_rows: list[dict[str, Any]] | None = None,
    sensor_rows: list[dict[str, Any]] | None = None,
    history_rows: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    source_files: list[str] | None = None,
    max_time_gap_s: float | None = None,
) -> dict[str, Any]:
    """Build aligned residual rows and metrics without writing files."""

    samples = align_run_tables(
        truth_rows=truth_rows or [],
        sensor_rows=sensor_rows or [],
        history_rows=history_rows or [],
        max_time_gap_s=max_time_gap_s,
    )
    estimator = SimpleFusionEstimator()
    residual_rows: list[dict[str, Any]] = []
    for sample in samples:
        sensor_source = _sensor_sources(sample)
        estimate = estimator.step(sample.time_s, _merged_source(sensor_source))
        residual_rows.append(_residual_row(sample, estimate))

    metric_rows = summarize_numeric_rows(
        residual_rows,
        exclude={"truth_time_delta_s", "sensor_time_delta_s", "history_time_delta_s"},
    )
    quality = {"gnss": availability_summary(residual_rows, available_key="gnss_available", quality_key="gnss_quality_score")}
    summary_warnings = list(dict.fromkeys(warnings or []))
    if samples and not any("truth_x_m" in row and "truth_z_m" in row for row in residual_rows):
        summary_warnings.append("truth position columns unavailable; position residuals were omitted")
    if samples and not any("gnss_available" in row for row in residual_rows):
        summary_warnings.append("GNSS channels unavailable; GNSS residual metrics were omitted")
    summary = _summary(
        residual_rows,
        metric_rows,
        source_files=source_files or [],
        warnings=summary_warnings,
        quality=quality,
        max_time_gap_s=max_time_gap_s,
    )
    return {"summary": summary, "metric_rows": metric_rows, "residuals": residual_rows}


def _residual_row(sample: AlignedSample, estimate: FusionEstimate) -> dict[str, Any]:
    truth_sources = _truth_sources(sample)
    sensor_sources = _sensor_sources(sample)
    row: dict[str, Any] = {
        "time_s": sample.time_s,
        "truth_time_delta_s": sample.truth_time_delta_s,
        "sensor_time_delta_s": sample.sensor_time_delta_s,
        "history_time_delta_s": sample.history_time_delta_s,
    }
    truth_position = _vector_from_sources(truth_sources, TRUTH_POSITION_KEYS)
    truth_velocity = _vector_from_sources(truth_sources, TRUTH_VELOCITY_KEYS)
    truth_rates = _truth_rates_rps(truth_sources)
    truth_accel = _truth_accel(truth_sources)
    truth_agl = _truth_agl_m(truth_sources, truth_position)
    truth_speed = _first_finite(truth_sources, "speed_mps")
    if truth_speed is None and truth_velocity is not None:
        truth_speed = _norm(truth_velocity)
    truth_airspeed = _first_finite(truth_sources, "airspeed_mps")
    if truth_airspeed is None:
        truth_airspeed = truth_speed

    _add_truth_streams(row, truth_position, truth_velocity, truth_rates, truth_accel, truth_speed, truth_airspeed)
    _add_estimate_streams(row, estimate, truth_position, truth_velocity)
    _add_gnss_streams(row, sensor_sources, truth_position, truth_velocity)
    _add_barometer_streams(row, sensor_sources, truth_position)
    _add_pitot_streams(row, sensor_sources, truth_airspeed)
    _add_radar_altimeter_streams(row, sensor_sources, truth_agl)
    _add_imu_streams(row, sensor_sources, truth_rates, truth_accel)
    return row


def _add_truth_streams(
    row: dict[str, Any],
    position: list[float] | None,
    velocity: list[float] | None,
    rates: list[float] | None,
    accel: list[float] | None,
    speed: float | None,
    airspeed: float | None,
) -> None:
    if position is not None:
        row.update({"truth_x_m": position[0], "truth_y_m": position[1], "truth_z_m": position[2]})
    if velocity is not None:
        row.update({"truth_vx_mps": velocity[0], "truth_vy_mps": velocity[1], "truth_vz_mps": velocity[2]})
    if rates is not None:
        row.update({"truth_p_rps": rates[0], "truth_q_rps": rates[1], "truth_r_rps": rates[2], "truth_body_rate_norm_rps": _norm(rates)})
    if accel is not None:
        row.update({"truth_ax_mps2": accel[0], "truth_ay_mps2": accel[1], "truth_az_mps2": accel[2], "truth_accel_norm_mps2": _norm(accel)})
    if speed is not None:
        row["truth_speed_mps"] = speed
    if airspeed is not None:
        row["truth_airspeed_mps"] = airspeed


def _add_estimate_streams(
    row: dict[str, Any],
    estimate: FusionEstimate,
    truth_position: list[float] | None,
    truth_velocity: list[float] | None,
) -> None:
    position = [estimate.x_m, estimate.y_m, estimate.z_m]
    velocity = [estimate.vx_mps, estimate.vy_mps, estimate.vz_mps]
    row.update(
        {
            "estimate_x_m": estimate.x_m,
            "estimate_y_m": estimate.y_m,
            "estimate_z_m": estimate.z_m,
            "estimate_vx_mps": estimate.vx_mps,
            "estimate_vy_mps": estimate.vy_mps,
            "estimate_vz_mps": estimate.vz_mps,
            "estimate_speed_mps": estimate.speed_mps,
            "estimate_gnss_used": 1.0 if estimate.gnss_used else 0.0,
            "estimate_barometer_used": 1.0 if estimate.barometer_used else 0.0,
            "estimate_pitot_used": 1.0 if estimate.pitot_used else 0.0,
            "estimate_radar_altimeter_used": 1.0 if estimate.radar_altimeter_used else 0.0,
            "gnss_quality_score": estimate.gnss_quality_score,
        }
    )
    if truth_position is not None:
        residual = _sub(position, truth_position)
        row.update(
            {
                "estimate_x_residual_m": residual[0],
                "estimate_y_residual_m": residual[1],
                "estimate_z_residual_m": residual[2],
                "estimate_position_error_m": _norm(residual),
            }
        )
    if truth_velocity is not None:
        residual = _sub(velocity, truth_velocity)
        row.update(
            {
                "estimate_vx_residual_mps": residual[0],
                "estimate_vy_residual_mps": residual[1],
                "estimate_vz_residual_mps": residual[2],
                "estimate_velocity_error_mps": _norm(residual),
            }
        )


def _add_gnss_streams(
    row: dict[str, Any],
    sources: list[dict[str, Any]],
    truth_position: list[float] | None,
    truth_velocity: list[float] | None,
) -> None:
    has_gnss = _has_any_key(sources, GPS_POSITION_KEYS + GPS_VELOCITY_KEYS + ("gps_valid", "gnss_valid"))
    if not has_gnss:
        return
    valid = _first_finite(sources, "gps_valid")
    if valid is None:
        valid = _first_finite(sources, "gnss_valid")
    position = _vector_from_sources(sources, GPS_POSITION_KEYS)
    velocity = _vector_from_sources(sources, GPS_VELOCITY_KEYS)
    available = (valid is None or valid > 0.5) and (position is not None or velocity is not None)
    row["gps_valid"] = valid
    row["gnss_available"] = 1.0 if available else 0.0
    latency = _first_finite(sources, "gps_latency_s")
    if latency is not None:
        row["gnss_latency_s"] = latency
    if position is not None:
        row.update({"sensor_gnss_x_m": position[0], "sensor_gnss_y_m": position[1], "sensor_gnss_z_m": position[2]})
        if available and truth_position is not None:
            residual = _sub(position, truth_position)
            row.update(
                {
                    "gnss_x_residual_m": residual[0],
                    "gnss_y_residual_m": residual[1],
                    "gnss_z_residual_m": residual[2],
                    "gnss_position_error_m": _norm(residual),
                }
            )
    if velocity is not None:
        row.update({"sensor_gnss_vx_mps": velocity[0], "sensor_gnss_vy_mps": velocity[1], "sensor_gnss_vz_mps": velocity[2]})
        if available and truth_velocity is not None:
            residual = _sub(velocity, truth_velocity)
            row.update(
                {
                    "gnss_vx_residual_mps": residual[0],
                    "gnss_vy_residual_mps": residual[1],
                    "gnss_vz_residual_mps": residual[2],
                    "gnss_velocity_error_mps": _norm(residual),
                }
            )


def _add_barometer_streams(row: dict[str, Any], sources: list[dict[str, Any]], truth_position: list[float] | None) -> None:
    value = _first_finite(sources, "baro_alt_m")
    if value is None:
        return
    row["sensor_baro_alt_m"] = value
    available = _channel_available(sources, "baro_valid")
    row["baro_available"] = 1.0 if available else 0.0
    bias = _first_finite(sources, "baro_bias_m")
    if bias is not None:
        row["sensor_baro_bias_m"] = bias
    if available and truth_position is not None:
        row["baro_altitude_residual_m"] = value - truth_position[2]


def _add_pitot_streams(row: dict[str, Any], sources: list[dict[str, Any]], truth_airspeed: float | None) -> None:
    value = _first_finite(sources, "pitot_airspeed_mps")
    if value is None:
        return
    row["sensor_pitot_airspeed_mps"] = value
    available = _channel_available(sources, "pitot_valid")
    row["pitot_available"] = 1.0 if available else 0.0
    qbar = _first_finite(sources, "pitot_qbar_pa")
    if qbar is not None:
        row["sensor_pitot_qbar_pa"] = qbar
    if available and truth_airspeed is not None:
        row["pitot_airspeed_residual_mps"] = value - truth_airspeed


def _add_radar_altimeter_streams(row: dict[str, Any], sources: list[dict[str, Any]], truth_agl_m: float | None) -> None:
    value = _first_finite(sources, "radar_agl_m")
    if value is None:
        return
    row["sensor_radar_agl_m"] = value
    available = _channel_available(sources, "radar_valid")
    row["radar_available"] = 1.0 if available else 0.0
    if available and truth_agl_m is not None:
        row["truth_agl_m"] = truth_agl_m
        row["radar_altitude_residual_m"] = value - truth_agl_m


def _add_imu_streams(
    row: dict[str, Any],
    sources: list[dict[str, Any]],
    truth_rates: list[float] | None,
    truth_accel: list[float] | None,
) -> None:
    has_imu = _has_any_key(sources, IMU_ACCEL_KEYS + GYRO_KEYS + ("imu_valid",))
    if not has_imu:
        return
    available = _channel_available(sources, "imu_valid")
    row["imu_available"] = 1.0 if available else 0.0
    accel = _vector_from_sources(sources, IMU_ACCEL_KEYS)
    gyro = _vector_from_sources(sources, GYRO_KEYS)
    if accel is not None:
        row.update({"sensor_imu_ax_mps2": accel[0], "sensor_imu_ay_mps2": accel[1], "sensor_imu_az_mps2": accel[2], "sensor_imu_accel_norm_mps2": _norm(accel)})
        if available and truth_accel is not None:
            residual = _sub(accel, truth_accel)
            row.update(
                {
                    "imu_ax_residual_mps2": residual[0],
                    "imu_ay_residual_mps2": residual[1],
                    "imu_az_residual_mps2": residual[2],
                    "imu_accel_norm_residual_mps2": _norm(accel) - _norm(truth_accel),
                }
            )
    if gyro is not None:
        row.update({"sensor_gyro_p_rps": gyro[0], "sensor_gyro_q_rps": gyro[1], "sensor_gyro_r_rps": gyro[2], "sensor_gyro_norm_rps": _norm(gyro)})
        if available and truth_rates is not None:
            residual = _sub(gyro, truth_rates)
            row.update(
                {
                    "gyro_p_residual_rps": residual[0],
                    "gyro_q_residual_rps": residual[1],
                    "gyro_r_residual_rps": residual[2],
                    "imu_gyro_norm_residual_rps": _norm(gyro) - _norm(truth_rates),
                }
            )


def _summary(
    residual_rows: list[dict[str, Any]],
    metric_rows: list[dict[str, Any]],
    *,
    source_files: list[str],
    warnings: list[str],
    quality: dict[str, Any],
    max_time_gap_s: float | None,
) -> dict[str, Any]:
    times = [_finite_or_none(row.get("time_s")) for row in residual_rows]
    finite_times = [value for value in times if value is not None]
    return {
        "row_count": len(residual_rows),
        "source_files": list(source_files),
        "warnings": list(dict.fromkeys(warnings)),
        "time_start_s": min(finite_times) if finite_times else None,
        "time_end_s": max(finite_times) if finite_times else None,
        "duration_s": (max(finite_times) - min(finite_times)) if finite_times else None,
        "max_time_gap_s": max_time_gap_s,
        "available_comparisons": _available_comparisons(residual_rows),
        "quality": quality,
        "metrics": metrics_by_name(metric_rows),
    }


def _available_comparisons(rows: list[dict[str, Any]]) -> list[str]:
    checks = {
        "gnss_position": "gnss_position_error_m",
        "gnss_velocity": "gnss_velocity_error_mps",
        "estimate_position": "estimate_position_error_m",
        "estimate_velocity": "estimate_velocity_error_mps",
        "barometer": "baro_altitude_residual_m",
        "pitot": "pitot_airspeed_residual_mps",
        "radar_altimeter": "radar_altitude_residual_m",
        "imu_acceleration": "imu_accel_norm_residual_mps2",
        "imu_gyro": "imu_gyro_norm_residual_rps",
    }
    return [name for name, key in checks.items() if any(_finite_or_none(row.get(key)) is not None for row in rows)]


def _write_plots(out: Path, rows: list[dict[str, Any]]) -> list[Path]:
    specs = [
        ("position_error.svg", ["estimate_position_error_m", "gnss_position_error_m"], "Position Error", "error (m)"),
        ("velocity_error.svg", ["estimate_velocity_error_mps", "gnss_velocity_error_mps"], "Velocity Error", "error (m/s)"),
        (
            "altitude_streams.svg",
            ["truth_z_m", "sensor_gnss_z_m", "sensor_baro_alt_m", "sensor_radar_agl_m", "estimate_z_m"],
            "Altitude Streams",
            "altitude (m)",
        ),
        (
            "speed_streams.svg",
            ["truth_speed_mps", "truth_airspeed_mps", "sensor_pitot_airspeed_mps", "estimate_speed_mps"],
            "Speed Streams",
            "speed (m/s)",
        ),
        ("gnss_quality.svg", ["gnss_quality_score", "gnss_available"], "GNSS Availability and Quality", "score"),
        (
            "aiding_residuals.svg",
            ["baro_altitude_residual_m", "pitot_airspeed_residual_mps", "radar_altitude_residual_m"],
            "Aiding Sensor Residuals",
            "residual",
        ),
        (
            "imu_gyro_residuals.svg",
            ["gyro_p_residual_rps", "gyro_q_residual_rps", "gyro_r_residual_rps", "imu_gyro_norm_residual_rps"],
            "IMU Gyro Residuals",
            "rad/s",
        ),
    ]
    paths: list[Path] = []
    for filename, keys, title, label in specs:
        available_keys = [key for key in keys if any(_finite_or_none(row.get(key)) is not None for row in rows)]
        if not available_keys:
            continue
        path = out / "plots" / filename
        write_time_plot(path, rows, available_keys, title, label)
        paths.append(path)
    return paths


def _write_html(out: Path, summary: dict[str, Any], metric_rows: list[dict[str, Any]], plots: list[Path]) -> Path:
    key_rows = "\n".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(_fmt(value))}</td></tr>"
        for key, value in summary.items()
        if key not in {"metrics", "quality", "artifacts"}
    )
    gnss = summary.get("quality", {}).get("gnss", {}) if isinstance(summary.get("quality"), dict) else {}
    quality_rows = "\n".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(_fmt(value))}</td></tr>" for key, value in gnss.items()
    )
    metric_html = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('metric', '')))}</td>"
        f"<td>{html.escape(str(row.get('kind', '')))}</td>"
        f"<td>{html.escape(_fmt(row.get('samples')))}</td>"
        f"<td>{html.escape(_fmt(row.get('current')))}</td>"
        f"<td>{html.escape(_fmt(row.get('min')))}</td>"
        f"<td>{html.escape(_fmt(row.get('max')))}</td>"
        f"<td>{html.escape(_fmt(row.get('rmse')))}</td>"
        "</tr>"
        for row in metric_rows[:80]
    ) or '<tr><td colspan="7">No finite metric rows were available.</td></tr>'
    plot_html = "\n".join(
        f'<figure><img src="{html.escape(str(path.relative_to(out)))}" alt="{html.escape(path.stem)}"><figcaption>{html.escape(path.stem.replace("_", " "))}</figcaption></figure>'
        for path in plots
    ) or "<p>No finite plot series were available.</p>"
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Estimation Fusion Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; background: #f7f8fa; }}
    main {{ max-width: 1120px; margin: 0 auto; }}
    table {{ border-collapse: collapse; background: white; margin: 18px 0; width: 100%; }}
    th, td {{ border: 1px solid #d9dee7; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; }}
    figure {{ background: white; border: 1px solid #d9dee7; margin: 18px 0; padding: 12px; }}
    img {{ width: 100%; height: auto; display: block; }}
    figcaption {{ font-size: 12px; color: #52616f; margin-top: 8px; }}
  </style>
</head>
<body>
<main>
  <h1>Estimation Fusion Report</h1>
  <p>Truth, sensor, and simple fused-estimate streams aligned by run time.</p>
  <h2>Summary</h2>
  <table>{key_rows}</table>
  <h2>GNSS Quality</h2>
  <table>{quality_rows}</table>
  <h2>Metrics</h2>
  <table>
    <thead><tr><th>Metric</th><th>Kind</th><th>Samples</th><th>Current</th><th>Min</th><th>Max</th><th>RMSE</th></tr></thead>
    <tbody>{metric_html}</tbody>
  </table>
  <h2>Plots</h2>
  {plot_html}
</main>
</body>
</html>
"""
    path = out / "estimation_report.html"
    path.write_text(doc)
    return path


def _truth_sources(sample: AlignedSample) -> list[dict[str, Any]]:
    return [source for source in (sample.truth, sample.history) if source]


def _sensor_sources(sample: AlignedSample) -> list[dict[str, Any]]:
    return [source for source in (sample.sensors, sample.history) if source]


def _merged_source(sources: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in reversed(sources):
        merged.update(source)
    return merged


def _vector_from_sources(sources: list[dict[str, Any]], keys: tuple[str, str, str]) -> list[float] | None:
    values = [_first_finite(sources, key) for key in keys]
    if all(value is not None for value in values):
        return [float(value) for value in values if value is not None]
    return None


def _truth_rates_rps(sources: list[dict[str, Any]]) -> list[float] | None:
    rates = _vector_from_sources(sources, ("p_rps", "q_rps", "r_rps"))
    if rates is not None:
        return rates
    dps = _vector_from_sources(sources, ("p_dps", "q_dps", "r_dps"))
    if dps is not None:
        return [math.radians(value) for value in dps]
    return None


def _truth_accel(sources: list[dict[str, Any]]) -> list[float] | None:
    for keys in TRUTH_ACCEL_KEY_SETS:
        accel = _vector_from_sources(sources, keys)
        if accel is not None:
            return accel
    return None


def _truth_agl_m(sources: list[dict[str, Any]], truth_position: list[float] | None) -> float | None:
    agl = _first_finite(sources, "altitude_agl_m")
    if agl is not None:
        return agl
    terrain = _first_finite(sources, "terrain_elevation_m")
    if terrain is not None and truth_position is not None:
        return truth_position[2] - terrain
    return truth_position[2] if truth_position is not None else None


def _first_finite(sources: list[dict[str, Any]], key: str) -> float | None:
    for source in sources:
        value = _finite_or_none(source.get(key))
        if value is not None:
            return value
    return None


def _has_any_key(sources: list[dict[str, Any]], keys: tuple[str, ...]) -> bool:
    return any(key in source for source in sources for key in keys)


def _channel_available(sources: list[dict[str, Any]], valid_key: str) -> bool:
    for source in sources:
        if valid_key not in source:
            continue
        value = _finite_or_none(source.get(valid_key))
        return value is not None and value > 0.5
    return True


def _sub(left: list[float], right: list[float]) -> list[float]:
    return [left[index] - right[index] for index in range(3)]


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


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
