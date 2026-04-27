"""Aerodynamic inspection, sweeps, and reports."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from aerosim6dof.config import load_json
from aerosim6dof.environment.atmosphere import isa_atmosphere
from aerosim6dof.reports.csv_writer import write_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.svg import write_xy_plot
from aerosim6dof.vehicle.aerodynamics import AerodynamicModel
from aerosim6dof.vehicle.geometry import ReferenceGeometry


def inspect_aero(vehicle_path: str | Path) -> dict[str, Any]:
    vehicle = load_json(vehicle_path)
    aero_cfg = vehicle.get("aero", {})
    model = AerodynamicModel(aero_cfg)
    geom = ReferenceGeometry.from_config(vehicle.get("reference", {}))
    checks = model.database.validate()
    return {
        "vehicle": vehicle.get("name", Path(vehicle_path).stem),
        "reference": geom.__dict__,
        "has_database": model.database.has_coefficients(),
        "database_errors": checks,
        "tables": sorted(aero_cfg.get("tables", {}).keys()),
        "compressibility": aero_cfg.get("compressibility", "none"),
        "stall_enabled": bool(aero_cfg.get("stall")),
        "derivatives": {
            key: aero_cfg[key]
            for key in sorted(aero_cfg)
            if key not in {"tables", "database", "stall", "uncertainty"}
        },
    }


def aero_sweep(
    vehicle_path: str | Path,
    out_dir: str | Path,
    mach_values: list[float] | None = None,
    alpha_deg_values: list[float] | None = None,
    beta_deg: float = 0.0,
    altitude_m: float = 0.0,
) -> dict[str, Any]:
    vehicle = load_json(vehicle_path)
    model = AerodynamicModel(vehicle.get("aero", {}))
    geom = ReferenceGeometry.from_config(vehicle.get("reference", {}))
    env = isa_atmosphere(altitude_m)
    mach_grid = mach_values or [0.2, 0.4, 0.6, 0.8, 0.95]
    alpha_grid = alpha_deg_values or list(np.linspace(-15.0, 25.0, 17))
    rows: list[dict[str, float]] = []
    for mach in mach_grid:
        speed = max(1.0, mach * env.speed_of_sound)
        for alpha_deg in alpha_grid:
            alpha = math.radians(alpha_deg)
            beta = math.radians(beta_deg)
            v_body = np.array(
                [
                    speed * math.cos(alpha) * math.cos(beta),
                    speed * math.sin(beta),
                    -speed * math.sin(alpha) * math.cos(beta),
                ],
                dtype=float,
            )
            sample = model.compute(
                env.density,
                env.speed_of_sound,
                v_body,
                np.zeros(3),
                {"elevator": 0.0, "aileron": 0.0, "rudder": 0.0},
                geom,
            )
            rows.append(
                {
                    "mach": float(mach),
                    "alpha_deg": float(alpha_deg),
                    "beta_deg": float(beta_deg),
                    "cd": sample.cd,
                    "cl": sample.cl,
                    "cy": sample.cy,
                    "cm": sample.cm,
                    "cn": sample.cn,
                    "cl_roll": sample.cl_roll,
                    "qbar_pa": sample.qbar_pa,
                }
            )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "aero_sweep.csv", rows)
    write_json(out / "aero_sweep_summary.json", _sweep_summary(rows, vehicle.get("name", Path(vehicle_path).stem)))
    for mach in mach_grid:
        subset = [r for r in rows if abs(r["mach"] - mach) < 1e-9]
        write_xy_plot(out / f"cl_cd_mach_{mach:.2f}.svg", subset, "alpha_deg", ["cl", "cd", "cm"], f"Aero Coefficients Mach {mach:.2f}", "alpha (deg)", "coefficient")
    return _sweep_summary(rows, vehicle.get("name", Path(vehicle_path).stem))


def aero_report(vehicle_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    summary = aero_sweep(vehicle_path, out)
    inspection = inspect_aero(vehicle_path)
    write_json(out / "aero_inspection.json", inspection)
    html = _aero_html(summary, inspection, sorted((out).glob("*.svg")))
    (out / "aero_report.html").write_text(html)
    return {"report": str(out / "aero_report.html"), "summary": summary, "inspection": inspection}


def _sweep_summary(rows: list[dict[str, float]], vehicle_name: str) -> dict[str, Any]:
    return {
        "vehicle": vehicle_name,
        "samples": len(rows),
        "max_cl": max(r["cl"] for r in rows),
        "min_cl": min(r["cl"] for r in rows),
        "max_cd": max(r["cd"] for r in rows),
        "min_cm": min(r["cm"] for r in rows),
        "max_cm": max(r["cm"] for r in rows),
    }


def _aero_html(summary: dict[str, Any], inspection: dict[str, Any], plots: list[Path]) -> str:
    plot_html = "\n".join(f'<figure><img src="{p.name}" alt="{p.stem}"><figcaption>{p.stem}</figcaption></figure>' for p in plots)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Aerodynamic Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; background: #f7f8fa; color: #1f2933; }}
    main {{ max-width: 1080px; margin: 0 auto; }}
    pre, figure {{ background: white; border: 1px solid #d9dee7; padding: 12px; }}
    img {{ width: 100%; height: auto; display: block; }}
  </style>
</head>
<body><main>
<h1>Aerodynamic Report</h1>
<h2>Summary</h2><pre>{json.dumps(summary, indent=2)}</pre>
<h2>Inspection</h2><pre>{json.dumps(inspection, indent=2)}</pre>
<h2>Coefficient Sweeps</h2>{plot_html}
</main></body></html>"""

