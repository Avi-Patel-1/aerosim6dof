"""Propulsion inspection and thrust-curve reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from aerosim6dof.config import load_json
from aerosim6dof.reports.csv_writer import write_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.svg import write_time_plot
from aerosim6dof.vehicle.propulsion import PropulsionModel


def inspect_propulsion(vehicle_path: str | Path) -> dict[str, Any]:
    vehicle = load_json(vehicle_path)
    prop_cfg = vehicle.get("propulsion", {})
    model = PropulsionModel(prop_cfg)
    return {
        "vehicle": vehicle.get("name", Path(vehicle_path).stem),
        "model": prop_cfg.get("model", "solid"),
        "max_thrust_n": model.max_thrust_n,
        "isp_s": model.isp_s,
        "burn_time_s": model.burn_time_s,
        "throttleable": model.throttleable,
        "has_thrust_curve": model.table is not None,
        "position_body_m": model.position_body_m.tolist(),
        "misalignment_deg": np.rad2deg(model.misalignment_rad).tolist(),
        "shutdown_intervals": prop_cfg.get("shutdown_intervals", []),
    }


def thrust_curve_report(vehicle_path: str | Path, out_dir: str | Path, samples: int = 160) -> dict[str, Any]:
    vehicle = load_json(vehicle_path)
    prop_cfg = vehicle.get("propulsion", {})
    model = PropulsionModel(prop_cfg)
    dry_mass = float(vehicle.get("dry_mass_kg", float(vehicle.get("mass_kg", 18.0)) * 0.75))
    mass = float(vehicle.get("mass_kg", 18.0))
    duration = max(model.burn_time_s * 1.2, model.burn_time_s + 1.0, 1.0)
    rows: list[dict[str, float]] = []
    impulse = 0.0
    previous_t = 0.0
    previous_thrust = 0.0
    times = np.linspace(0.0, duration, max(2, samples))
    dt = float(times[1] - times[0]) if len(times) > 1 else None
    for t in times:
        sample = model.sample(float(t), 1.0, mass, dry_mass, dt=dt)
        impulse += 0.5 * (previous_thrust + sample.thrust_n) * max(0.0, float(t) - previous_t)
        previous_t = float(t)
        previous_thrust = sample.thrust_n
        rows.append(
            {
                "time_s": float(t),
                "thrust_n": sample.thrust_n,
                "mass_flow_kgps": sample.mass_flow_kgps,
                "impulse_n_s": impulse,
                "throttle_actual": sample.throttle_actual,
            }
        )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "vehicle": vehicle.get("name", Path(vehicle_path).stem),
        "samples": len(rows),
        "burn_time_s": model.burn_time_s,
        "peak_thrust_n": max(r["thrust_n"] for r in rows),
        "total_impulse_n_s": rows[-1]["impulse_n_s"],
        "average_thrust_n": rows[-1]["impulse_n_s"] / max(model.burn_time_s, 1e-9),
    }
    write_csv(out / "thrust_curve.csv", rows)
    write_json(out / "thrust_curve_summary.json", summary)
    write_time_plot(out / "thrust_curve.svg", rows, ["thrust_n"], "Thrust Curve", "thrust (N)")
    write_time_plot(out / "mass_flow.svg", rows, ["mass_flow_kgps"], "Mass Flow", "kg/s")
    (out / "thrust_curve_report.html").write_text(_html(summary, ["thrust_curve.svg", "mass_flow.svg"]))
    return {"report": str(out / "thrust_curve_report.html"), "summary": summary}


def _html(summary: dict[str, Any], plots: list[str]) -> str:
    figures = "\n".join(f'<figure><img src="{p}" alt="{p}"></figure>' for p in plots)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Propulsion Report</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;background:#f7f8fa;color:#1f2933}}main{{max-width:980px;margin:0 auto}}pre,figure{{background:white;border:1px solid #d9dee7;padding:12px}}img{{width:100%}}</style>
</head><body><main><h1>Propulsion Report</h1><pre>{json.dumps(summary, indent=2)}</pre>{figures}</main></body></html>"""
