"""Run comparison helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aerosim6dof.reports.csv_writer import read_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.svg import write_time_plot


def compare_histories(a_path: str | Path, b_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    a = read_csv(a_path)
    b = read_csv(b_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    n = min(len(a), len(b))
    rows = []
    for i in range(n):
        rows.append(
            {
                "time_s": float(a[i].get("time_s", i)),
                "altitude_delta_m": float(b[i].get("altitude_m", 0.0)) - float(a[i].get("altitude_m", 0.0)),
                "crossrange_delta_m": float(b[i].get("y_m", 0.0)) - float(a[i].get("y_m", 0.0)),
                "speed_delta_mps": float(b[i].get("speed_mps", 0.0)) - float(a[i].get("speed_mps", 0.0)),
            }
        )
    summary = {
        "samples_compared": n,
        "final_altitude_delta_m": rows[-1]["altitude_delta_m"] if rows else 0.0,
        "final_crossrange_delta_m": rows[-1]["crossrange_delta_m"] if rows else 0.0,
        "final_speed_delta_mps": rows[-1]["speed_delta_mps"] if rows else 0.0,
    }
    write_json(out / "compare_summary.json", summary)
    if rows:
        write_time_plot(out / "compare_altitude_delta.svg", rows, ["altitude_delta_m"], "Altitude Delta", "delta altitude (m)")
        write_time_plot(out / "compare_crossrange_delta.svg", rows, ["crossrange_delta_m"], "Crossrange Delta", "delta crossrange (m)")
        write_time_plot(out / "compare_speed_delta.svg", rows, ["speed_delta_mps"], "Speed Delta", "delta speed (m/s)")
    return summary

