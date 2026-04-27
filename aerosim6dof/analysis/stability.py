"""Linear-model stability and trim-sweep analysis."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from aerosim6dof.config import load_json
from aerosim6dof.gnc.trim import simple_trim
from aerosim6dof.reports.csv_writer import write_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.svg import write_xy_plot


def stability_report(linearization_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    """Analyze a saved linearization and write eigenvalue/stability artifacts."""

    linearization = load_json(linearization_path)
    a_mat = np.asarray(linearization["A"], dtype=float)
    state_order = list(linearization.get("state_order", [f"x{i}" for i in range(a_mat.shape[0])]))
    eigvals, eigvecs = np.linalg.eig(a_mat)
    rows = _eigen_rows(eigvals, eigvecs, state_order)
    unstable = [row for row in rows if float(row["real"]) > 1e-7]
    modes = _mode_summary(rows)
    result = {
        "stable": not unstable,
        "state_order": state_order,
        "eigenvalues": rows,
        "modes": modes,
        "unstable_count": len(unstable),
        "max_real_part": max(float(row["real"]) for row in rows) if rows else None,
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "stability.json", result)
    write_csv(out / "eigenvalues.csv", rows)
    plot_path = out / "eigenvalue_map.svg"
    write_xy_plot(plot_path, rows, "real", ["imag"], "Eigenvalue Map", "real", "imaginary")
    report_path = _write_stability_html(out, result, [plot_path])
    result["report"] = str(report_path)
    return result


def trim_sweep(
    vehicle_path: str | Path,
    out_dir: str | Path,
    speeds_mps: list[float],
    altitudes_m: list[float],
) -> dict[str, Any]:
    """Run simple trim over a speed/altitude grid."""

    vehicle = load_json(vehicle_path)
    rows: list[dict[str, Any]] = []
    for altitude in altitudes_m:
        for speed in speeds_mps:
            trim = simple_trim(vehicle, speed, altitude)
            rows.append(
                {
                    "speed_mps": float(speed),
                    "altitude_m": float(altitude),
                    "alpha_deg": float(trim["alpha_deg"]),
                    "pitch_deg": float(trim["pitch_deg"]),
                    "elevator_deg": float(trim["elevator_deg"]),
                    "residual_score": float(trim["residual_score"]),
                    "feasible": float(trim["residual_score"]) < 1500.0,
                }
            )
    result = {
        "vehicle": str(vehicle_path),
        "count": len(rows),
        "speed_range_mps": [min(speeds_mps), max(speeds_mps)] if speeds_mps else [],
        "altitude_range_m": [min(altitudes_m), max(altitudes_m)] if altitudes_m else [],
        "rows": rows,
        "feasible_count": sum(1 for row in rows if row["feasible"]),
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "trim_sweep.json", result)
    write_csv(out / "trim_sweep.csv", rows)
    plots = [
        out / "trim_alpha_vs_speed.svg",
        out / "trim_elevator_vs_speed.svg",
        out / "trim_residual_vs_speed.svg",
    ]
    write_xy_plot(plots[0], rows, "speed_mps", ["alpha_deg"], "Trim Alpha", "speed (m/s)", "alpha (deg)")
    write_xy_plot(plots[1], rows, "speed_mps", ["elevator_deg"], "Trim Elevator", "speed (m/s)", "elevator (deg)")
    write_xy_plot(plots[2], rows, "speed_mps", ["residual_score"], "Trim Residual", "speed (m/s)", "score")
    report_path = _write_trim_html(out, result, plots)
    result["report"] = str(report_path)
    return result


def linear_model_report(linearization_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    """Write matrix dimensions, norms, and stability artifacts for a linear model."""

    linearization = load_json(linearization_path)
    a_mat = np.asarray(linearization["A"], dtype=float)
    b_mat = np.asarray(linearization["B"], dtype=float)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stability = stability_report(linearization_path, out / "stability")
    result = {
        "state_count": int(a_mat.shape[0]),
        "control_count": int(b_mat.shape[1]) if b_mat.ndim == 2 else 0,
        "a_frobenius_norm": float(np.linalg.norm(a_mat)),
        "b_frobenius_norm": float(np.linalg.norm(b_mat)),
        "a_rank": int(np.linalg.matrix_rank(a_mat)),
        "b_rank": int(np.linalg.matrix_rank(b_mat)),
        "stability": {
            "stable": stability["stable"],
            "unstable_count": stability["unstable_count"],
            "max_real_part": stability["max_real_part"],
        },
    }
    write_json(out / "linear_model_report.json", result)
    _write_linear_html(out, result)
    result["report"] = str(out / "linear_model_report.html")
    return result


def _eigen_rows(eigvals: np.ndarray, eigvecs: np.ndarray, state_order: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, eig in enumerate(eigvals):
        real = float(np.real(eig))
        imag = float(np.imag(eig))
        wn = float(abs(eig))
        damping = float(-real / wn) if wn > 1e-12 else None
        time_constant = float(-1.0 / real) if real < -1e-12 else None
        period = float(2.0 * math.pi / abs(imag)) if abs(imag) > 1e-12 else None
        vector = eigvecs[:, idx]
        dominant_idx = int(np.argmax(np.abs(vector)))
        dominant_state = state_order[dominant_idx] if dominant_idx < len(state_order) else f"x{dominant_idx}"
        rows.append(
            {
                "index": idx,
                "real": real,
                "imag": imag,
                "frequency_radps": abs(imag),
                "natural_frequency_radps": wn,
                "damping_ratio": damping,
                "time_constant_s": time_constant,
                "period_s": period,
                "dominant_state": dominant_state,
                "mode": _identify_mode(real, imag, dominant_state),
                "stable": real <= 1e-7,
            }
        )
    return rows


def _identify_mode(real: float, imag: float, dominant_state: str) -> str:
    state = dominant_state.lower()
    if real > 1e-7:
        return "unstable"
    if abs(imag) > 1e-3:
        if state in {"r", "vy", "yaw", "y", "p", "qx", "qz"}:
            return "dutch_roll"
        if state in {"q", "vz", "pitch"} or abs(imag) > 1.0:
            return "short_period"
        return "phugoid"
    if state == "p":
        return "roll_subsidence"
    if state in {"r", "vy", "yaw", "y"}:
        return "spiral"
    if state in {"q", "vz"}:
        return "aperiodic_pitch"
    return "real_mode"


def _mode_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for row in rows:
        mode = str(row["mode"])
        current = summary.get(mode)
        if current is None or float(row["real"]) > float(current["real"]):
            summary[mode] = row
    return summary


def _write_stability_html(out: Path, result: dict[str, Any], plots: list[Path]) -> Path:
    mode_rows = "\n".join(
        f"<tr><td>{html.escape(mode)}</td><td>{_fmt(row.get('real'))}</td><td>{_fmt(row.get('imag'))}</td><td>{html.escape(str(row.get('dominant_state')))}</td></tr>"
        for mode, row in sorted(result.get("modes", {}).items())
    )
    plot_html = "\n".join(f'<figure><img src="{html.escape(str(p.relative_to(out)))}" alt="{html.escape(p.stem)}"></figure>' for p in plots)
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Stability Report</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;color:#1f2933;background:#f7f8fa}}main{{max-width:1040px;margin:0 auto}}table{{border-collapse:collapse;background:white;margin:18px 0}}th,td{{border:1px solid #d9dee7;padding:8px 10px;text-align:left}}th{{background:#eef2f7}}figure{{background:white;border:1px solid #d9dee7;padding:12px}}</style>
</head><body><main>
<h1>Stability Report</h1>
<p>Stable: {html.escape(str(result.get("stable")))}; unstable modes: {html.escape(str(result.get("unstable_count")))}; max real part: {_fmt(result.get("max_real_part"))}</p>
<h2>Mode Summary</h2>
<table><tr><th>Mode</th><th>Real</th><th>Imaginary</th><th>Dominant State</th></tr>{mode_rows}</table>
{plot_html}
</main></body></html>
"""
    path = out / "stability_report.html"
    path.write_text(doc)
    return path


def _write_trim_html(out: Path, result: dict[str, Any], plots: list[Path]) -> Path:
    rows = "\n".join(
        f"<tr><td>{_fmt(row['speed_mps'])}</td><td>{_fmt(row['altitude_m'])}</td><td>{_fmt(row['alpha_deg'])}</td><td>{_fmt(row['elevator_deg'])}</td><td>{_fmt(row['residual_score'])}</td><td>{html.escape(str(row['feasible']))}</td></tr>"
        for row in result["rows"]
    )
    plot_html = "\n".join(f'<figure><img src="{html.escape(p.name)}" alt="{html.escape(p.stem)}"></figure>' for p in plots)
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Trim Sweep</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;color:#1f2933;background:#f7f8fa}}main{{max-width:1040px;margin:0 auto}}table{{border-collapse:collapse;background:white;margin:18px 0}}th,td{{border:1px solid #d9dee7;padding:8px 10px;text-align:left}}th{{background:#eef2f7}}figure{{background:white;border:1px solid #d9dee7;padding:12px}}img{{width:100%;height:auto}}</style>
</head><body><main>
<h1>Trim Sweep</h1>
<p>{result["count"]} trim points; feasible points: {result["feasible_count"]}</p>
<table><tr><th>Speed</th><th>Altitude</th><th>Alpha</th><th>Elevator</th><th>Residual</th><th>Feasible</th></tr>{rows}</table>
{plot_html}
</main></body></html>
"""
    path = out / "trim_sweep_report.html"
    path.write_text(doc)
    return path


def _write_linear_html(out: Path, result: dict[str, Any]) -> Path:
    rows = "\n".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(_fmt(v))}</td></tr>" for k, v in result.items() if k != "stability")
    stability = result["stability"]
    rows += "\n".join(f"<tr><th>stability.{html.escape(k)}</th><td>{html.escape(_fmt(v))}</td></tr>" for k, v in stability.items())
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Linear Model Report</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;color:#1f2933;background:#f7f8fa}}main{{max-width:900px;margin:0 auto}}table{{border-collapse:collapse;background:white;margin:18px 0}}th,td{{border:1px solid #d9dee7;padding:8px 10px;text-align:left}}th{{background:#eef2f7}}</style>
</head><body><main><h1>Linear Model Report</h1><table>{rows}</table><p>See <code>stability/stability_report.html</code> for eigenvalue details.</p></main></body></html>
"""
    path = out / "linear_model_report.html"
    path.write_text(doc)
    return path


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if value is None:
        return "-"
    return str(value)
