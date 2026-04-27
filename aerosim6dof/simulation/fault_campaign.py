"""Fault campaign runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aerosim6dof.config import deep_merge
from aerosim6dof.reports.csv_writer import write_csv
from aerosim6dof.reports.html import write_batch_report
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.scenario import Scenario

from .runner import run_scenario


FAULT_LIBRARY: dict[str, dict[str, Any]] = {
    "gps_dropout": {
        "description": "GPS outage during closed-loop flight.",
        "patch": {
            "guidance": {"navigation": "noisy_sensors"},
            "sensors": {"faults": [{"sensor": "gps", "type": "dropout", "start_s": 6.0, "end_s": 10.0}]},
        },
    },
    "imu_bias": {
        "description": "Step bias on accelerometers and pitch gyro.",
        "patch": {
            "sensors": {
                "faults": [
                    {
                        "sensor": "imu",
                        "type": "bias_jump",
                        "start_s": 5.0,
                        "end_s": 99.0,
                        "accel_bias_mps2": [0.35, -0.12, 0.25],
                        "gyro_bias_rps": [0.0, 0.018, 0.0],
                    }
                ]
            }
        },
    },
    "barometer_bias": {
        "description": "Weather-driven barometric altitude bias.",
        "patch": {
            "sensors": {"faults": [{"sensor": "barometer", "type": "bias_jump", "start_s": 7.0, "end_s": 99.0, "bias_m": 35.0}]}
        },
    },
    "pitot_blockage": {
        "description": "Partial pitot blockage reducing measured airspeed.",
        "patch": {"sensors": {"pitot": {"blockage_fraction": 0.35}}},
    },
    "mag_dropout": {
        "description": "Magnetometer outage during heading-hold segment.",
        "patch": {"sensors": {"faults": [{"sensor": "magnetometer", "type": "dropout", "start_s": 4.0, "end_s": 9.0}]}},
    },
    "thrust_loss": {
        "description": "Temporary engine shutdown with restart allowed.",
        "patch": {"vehicle": {"propulsion": {"shutdown_intervals": [[6.5, 10.5]], "restart_allowed": True}}},
    },
    "stuck_elevator": {
        "description": "Elevator locks at a nose-down deflection.",
        "patch": {
            "vehicle": {
                "actuators": {
                    "surfaces": {
                        "elevator": {"failure": {"mode": "stuck", "start_s": 6.0, "value_rad": -0.1}}
                    }
                }
            }
        },
    },
}


def run_fault_campaign(
    scenario: Scenario,
    out_dir: str | Path,
    faults: list[str] | None = None,
    max_runs: int = 50,
) -> dict[str, Any]:
    """Run a scenario once per named fault from the built-in library."""

    names = faults or sorted(FAULT_LIBRARY)
    unknown = [name for name in names if name not in FAULT_LIBRARY]
    if unknown:
        raise ValueError(f"unknown fault(s): {', '.join(unknown)}")
    if len(names) > max_runs:
        raise ValueError(f"fault campaign would create {len(names)} runs, above max_runs={max_runs}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    for name in names:
        entry = FAULT_LIBRARY[name]
        data = json.loads(json.dumps(scenario.raw))
        data["name"] = f"{scenario.name}_{name}"
        data = deep_merge(data, entry["patch"])
        run_out = out / name
        summary = run_scenario(Scenario.from_dict(data, source_path=scenario.source_path), run_out)
        summary["fault_name"] = name
        summary["fault_description"] = entry["description"]
        summary["run_dir"] = str(run_out)
        summaries.append(summary)
    result = {
        "scenario": scenario.name,
        "kind": "fault_campaign",
        "count": len(summaries),
        "faults": names,
        "runs": summaries,
    }
    write_json(out / "fault_campaign_summary.json", result)
    write_json(out / "batch_summary.json", result)
    write_csv(out / "fault_campaign_index.csv", _index_rows(summaries))
    write_batch_report(out, result, filename="fault_campaign_report.html")
    return result


def _index_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        final = summary.get("final", {}) if isinstance(summary.get("final"), dict) else {}
        rows.append(
            {
                "fault_name": summary.get("fault_name", ""),
                "scenario": summary.get("scenario", ""),
                "duration_s": summary.get("duration_s", ""),
                "final_altitude_m": final.get("altitude_m", ""),
                "final_speed_mps": final.get("speed_mps", ""),
                "max_qbar_pa": summary.get("max_qbar_pa", ""),
                "max_load_factor_g": summary.get("max_load_factor_g", ""),
                "event_count": summary.get("event_count", ""),
                "run_dir": summary.get("run_dir", ""),
            }
        )
    return rows
