"""Parameter sweep campaign runner."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

from aerosim6dof.config import deep_merge
from aerosim6dof.reports.csv_writer import write_csv
from aerosim6dof.reports.html import write_batch_report
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.scenario import Scenario

from .runner import run_scenario


def run_sweep_campaign(
    scenario: Scenario,
    out_dir: str | Path,
    sweep: dict[str, list[Any]],
    max_runs: int = 200,
) -> dict[str, Any]:
    """Run a Cartesian sweep over dotted scenario fields."""

    if not sweep:
        raise ValueError("sweep must contain at least one parameter")
    keys = list(sweep)
    values = [sweep[key] for key in keys]
    if any(not isinstance(v, list) or not v for v in values):
        raise ValueError("each sweep parameter must be a non-empty list")
    combinations = list(itertools.product(*values))
    if len(combinations) > max_runs:
        raise ValueError(f"sweep expands to {len(combinations)} runs, above max_runs={max_runs}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    for idx, combo in enumerate(combinations):
        patch: dict[str, Any] = {}
        labels = []
        for key, value in zip(keys, combo):
            _set_dotted(patch, key, value)
            labels.append(f"{key}={value}")
        data = deep_merge(json.loads(json.dumps(scenario.raw)), patch)
        data["name"] = f"{scenario.name}_sweep_{idx:03d}"
        run_out = out / data["name"]
        summary = run_scenario(Scenario.from_dict(data, source_path=scenario.source_path), run_out)
        summary["sweep_index"] = idx
        summary["parameters"] = dict(zip(keys, combo))
        summary["label"] = ", ".join(labels)
        summary["run_dir"] = str(run_out)
        summaries.append(summary)
    campaign = {
        "base_scenario": scenario.name,
        "count": len(summaries),
        "parameters": sweep,
        "runs": summaries,
        "best_by_final_altitude": _best(summaries, "final", "altitude_m"),
        "worst_by_max_load": _worst(summaries, "max_load_factor_g"),
    }
    write_json(out / "campaign_summary.json", campaign)
    write_json(out / "batch_summary.json", {"runs": summaries, "count": len(summaries), "kind": "sweep"})
    write_csv(out / "campaign_index.csv", _campaign_rows(summaries))
    write_batch_report(out, {"runs": summaries, "count": len(summaries)}, filename="campaign_report.html")
    return campaign


def _set_dotted(target: dict[str, Any], dotted: str, value: Any) -> None:
    cur = target
    parts = dotted.split(".")
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _best(summaries: list[dict[str, Any]], section: str, key: str) -> dict[str, Any] | None:
    if not summaries:
        return None
    return max(summaries, key=lambda s: float(s.get(section, {}).get(key, float("-inf"))))


def _worst(summaries: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    if not summaries:
        return None
    return max(summaries, key=lambda s: float(s.get(key, float("-inf"))))


def _campaign_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for s in summaries:
        final = s.get("final", {})
        row = {
            "sweep_index": s.get("sweep_index"),
            "scenario": s.get("scenario"),
            "label": s.get("label"),
            "duration_s": s.get("duration_s"),
            "final_altitude_m": final.get("altitude_m"),
            "final_speed_mps": final.get("speed_mps"),
            "max_qbar_pa": s.get("max_qbar_pa"),
            "max_load_factor_g": s.get("max_load_factor_g"),
            "event_count": s.get("event_count"),
            "run_dir": s.get("run_dir"),
        }
        for key, value in s.get("parameters", {}).items():
            row[f"param_{key}"] = value
        rows.append(row)
    return rows

