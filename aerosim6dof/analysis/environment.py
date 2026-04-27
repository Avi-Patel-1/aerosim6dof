"""Environment profile and report utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from aerosim6dof.config import load_with_optional_base
from aerosim6dof.environment.atmosphere import isa_atmosphere
from aerosim6dof.environment.gravity import gravity_magnitude
from aerosim6dof.environment.wind import WindModel
from aerosim6dof.reports.csv_writer import write_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.svg import write_xy_plot


def environment_report(environment_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    env_cfg = load_with_optional_base(environment_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    altitudes = np.linspace(0.0, 25000.0, 101)
    wind = WindModel(env_cfg.get("wind", {}), seed=3)
    rows: list[dict[str, float]] = []
    for alt in altitudes:
        atm = isa_atmosphere(float(alt))
        w = wind.deterministic(10.0, np.array([0.0, 0.0, alt], dtype=float))
        rows.append(
            {
                "altitude_m": float(alt),
                "density_kgpm3": atm.density,
                "pressure_pa": atm.pressure,
                "temperature_k": atm.temperature,
                "speed_of_sound_mps": atm.speed_of_sound,
                "gravity_mps2": gravity_magnitude(float(alt)),
                "wind_x_mps": float(w[0]),
                "wind_y_mps": float(w[1]),
                "wind_z_mps": float(w[2]),
            }
        )
    summary = {
        "environment": env_cfg.get("name", Path(environment_path).stem),
        "samples": len(rows),
        "surface_density_kgpm3": rows[0]["density_kgpm3"],
        "top_density_kgpm3": rows[-1]["density_kgpm3"],
        "max_wind_mps": max((r["wind_x_mps"] ** 2 + r["wind_y_mps"] ** 2 + r["wind_z_mps"] ** 2) ** 0.5 for r in rows),
    }
    write_csv(out / "environment_profile.csv", rows)
    write_json(out / "environment_summary.json", summary)
    write_xy_plot(out / "density_profile.svg", rows, "altitude_m", ["density_kgpm3"], "Density Profile", "altitude (m)", "density (kg/m^3)")
    write_xy_plot(out / "pressure_profile.svg", rows, "altitude_m", ["pressure_pa"], "Pressure Profile", "altitude (m)", "pressure (Pa)")
    write_xy_plot(out / "wind_profile.svg", rows, "altitude_m", ["wind_x_mps", "wind_y_mps", "wind_z_mps"], "Wind Profile", "altitude (m)", "wind (m/s)")
    (out / "environment_report.html").write_text(_html(summary, ["density_profile.svg", "pressure_profile.svg", "wind_profile.svg"]))
    return {"report": str(out / "environment_report.html"), "summary": summary}


def _html(summary: dict[str, Any], plots: list[str]) -> str:
    figures = "\n".join(f'<figure><img src="{p}" alt="{p}"></figure>' for p in plots)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Environment Report</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;background:#f7f8fa;color:#1f2933}}main{{max-width:980px;margin:0 auto}}pre,figure{{background:white;border:1px solid #d9dee7;padding:12px}}img{{width:100%}}</style>
</head><body><main><h1>Environment Report</h1><pre>{json.dumps(summary, indent=2)}</pre>{figures}</main></body></html>"""

