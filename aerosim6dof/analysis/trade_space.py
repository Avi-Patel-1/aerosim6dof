"""Trade-space analysis layer built on AeroLab 6DOF run outputs."""

from __future__ import annotations

import csv
import json
import math
import operator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from aerosim6dof.config import deep_merge
from aerosim6dof.reports.csv_writer import read_csv, write_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.svg import write_xy_plot
from aerosim6dof.scenario import Scenario
from aerosim6dof.simulation.runner import run_scenario
from aerosim6dof.tradespace import core


DEFAULT_OBJECTIVES = core.DEFAULT_OBJECTIVES


def run_trade_space_study(
    scenario: Scenario,
    out_dir: str | Path,
    *,
    samples: int = 8,
    seed: int = 2026,
    parameters: dict[str, list[Any]] | None = None,
    dispersions: dict[str, float] | None = None,
    objectives: list[dict[str, Any]] | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a bounded design study through the real AeroLab simulator."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    design_cases = _design_cases(scenario, samples=samples, seed=seed, parameters=parameters, dispersions=dispersions)
    sample_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    for index, case in enumerate(design_cases):
        data = deep_merge(json.loads(json.dumps(scenario.raw)), case["patch"])
        data["name"] = f"{scenario.name}_trade_{index:03d}"
        run_out = out / "runs" / data["name"]
        summary = run_scenario(Scenario.from_dict(data, source_path=scenario.source_path), run_out)
        sample = {"run": index, "seed": case["seed"], **case["sample"]}
        result = load_run_as_trade_result(run_out, run_index=index, sample=sample, summary=summary)
        sample_rows.append(sample)
        result_rows.append(result)
        run_records.append({"run": index, "seed": case["seed"], "run_dir": str(run_out), "status": "complete"})
    return write_trade_space_artifacts(
        out,
        sample_rows,
        result_rows,
        study_name=f"{scenario.name} trade space",
        objectives=objectives,
        constraints=constraints,
        source={"scenario": scenario.name, "samples": samples, "seed": seed},
        run_records=run_records,
    )


def analyze_existing_runs(
    run_dirs: list[str | Path],
    out_dir: str | Path,
    *,
    study_name: str = "Existing run trade space",
    objectives: list[dict[str, Any]] | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = Path(out_dir)
    sample_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    for index, run_dir in enumerate(run_dirs):
        run = Path(run_dir)
        sample = load_run_sample(run, run_index=index)
        result = load_run_as_trade_result(run, run_index=index, sample=sample)
        sample_rows.append(sample)
        result_rows.append(result)
        run_records.append({"run": index, "run_dir": str(run), "status": "indexed"})
    return write_trade_space_artifacts(
        out,
        sample_rows,
        result_rows,
        study_name=study_name,
        objectives=objectives,
        constraints=constraints,
        source={"run_count": len(run_dirs), "mode": "existing_runs"},
        run_records=run_records,
    )


def run_trade_space_sweep(
    scenario: Scenario,
    out_dir: str | Path,
    *,
    parameter: str,
    values: list[Any],
    objectives: list[dict[str, Any]] | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_trade_space_study(
        scenario,
        out_dir,
        samples=len(values),
        parameters={parameter: values},
        objectives=objectives,
        constraints=constraints,
    )


def run_trade_space_campaign(
    scenario: Scenario,
    out_dir: str | Path,
    *,
    seed: int = 2026,
    samples: int = 8,
) -> dict[str, Any]:
    """Run a compact campaign with baseline, dispersion, and throttle sweep studies."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    studies = [
        (
            "baseline_dispersion",
            run_trade_space_study(
                scenario,
                out / "baseline_dispersion",
                samples=samples,
                seed=seed,
                dispersions={"vehicle.mass_kg": 0.25, "wind.steady_mps.0": 0.3},
            ),
        ),
        (
            "throttle_sweep",
            run_trade_space_study(
                scenario,
                out / "throttle_sweep",
                samples=3,
                seed=seed + 100,
                parameters={"guidance.throttle": [0.76, 0.86, 0.96]},
            ),
        ),
        (
            "pitch_sweep",
            run_trade_space_study(
                scenario,
                out / "pitch_sweep",
                samples=3,
                seed=seed + 200,
                parameters={"initial.euler_deg.1": [2.0, 6.0, 10.0]},
            ),
        ),
    ]
    rows = []
    for name, summary in studies:
        best = summary.get("best_design", {}) if isinstance(summary, dict) else {}
        rows.append(
            {
                "study": name,
                "scenario": name,
                "runs": summary.get("runs", 0),
                "success_probability": summary.get("reliability", {}).get("success_probability"),
                "pareto_rows": summary.get("pareto_rows", 0),
                "best_scenario": best.get("scenario"),
                "best_miss_distance_m": best.get("miss_distance_m"),
                "best_max_qbar_pa": best.get("max_qbar_pa"),
                "miss_distance_m": best.get("miss_distance_m"),
                "max_qbar_pa": best.get("max_qbar_pa"),
                "robustness_margin": best.get("robustness_margin"),
            }
        )
    write_csv(out / "campaign_summary.csv", rows)
    payload = {
        "kind": "trade_space_campaign",
        "scenario": scenario.name,
        "studies": rows,
        "ranked_preview": rows,
        "generated_at_utc": _utc_now(),
    }
    write_json(out / "campaign_rollup.json", payload)
    write_trade_space_report(out, payload, rows, [], [], title="Trade Space Campaign")
    return payload


def load_run_as_trade_result(
    run_dir: str | Path,
    *,
    run_index: int = 0,
    sample: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = Path(run_dir)
    summary = summary or _read_json(run / "summary.json")
    history = read_csv(run / "history.csv") if (run / "history.csv").exists() else []
    events = _read_json(run / "events.json") if (run / "events.json").exists() else []
    final = summary.get("final", {}) if isinstance(summary.get("final"), dict) else {}
    miss_distance = _first_number(summary.get("min_interceptor_range_m"), summary.get("min_target_range_m"), summary.get("min_target_distance_m"))
    max_load = _first_number(summary.get("max_load_factor_g"), summary.get("max_load_g"))
    impulse = _integrate(history, "thrust_n")
    max_qbar = _first_number(summary.get("max_qbar_pa"), _max(history, "qbar_pa"), default=0.0)
    success, failure_reason = _classify_success(summary, events, miss_distance, max_qbar, max_load)
    robustness_margin = _robustness_margin(summary, miss_distance, max_qbar, max_load)
    row = {
        "run": run_index,
        "scenario": summary.get("scenario", run.name),
        "success": success,
        "failed": not success,
        "failure_reason": failure_reason,
        "miss_distance_m": miss_distance,
        "final_altitude_m": _first_number(final.get("altitude_agl_m"), final.get("altitude_m"), default=math.nan),
        "terminal_speed_mps": _first_number(final.get("speed_mps"), default=math.nan),
        "time_of_flight_s": _first_number(final.get("time_s"), summary.get("duration_s"), default=math.nan),
        "max_altitude_m": _first_number(summary.get("max_altitude_m"), default=math.nan),
        "max_qbar_pa": max_qbar,
        "max_load_g": max_load,
        "max_load_factor_g": max_load,
        "impulse_n_s": impulse,
        "robustness_margin": robustness_margin,
        "event_count": int(summary.get("event_count", len(events) if isinstance(events, list) else 0) or 0),
        "samples": int(summary.get("samples", len(history)) or 0),
        "run_dir": str(run),
    }
    if sample:
        for key, value in sample.items():
            if key not in row:
                row[f"sample_{key}" if key in {"scenario", "success"} else key] = value
    return row


def load_run_sample(run_dir: str | Path, *, run_index: int = 0) -> dict[str, Any]:
    run = Path(run_dir)
    scenario = _read_json(run / "scenario_resolved.json") if (run / "scenario_resolved.json").exists() else {}
    wind = scenario.get("wind", {}) if isinstance(scenario.get("wind"), dict) else {}
    steady = wind.get("steady_mps", [0.0, 0.0, 0.0])
    vehicle = scenario.get("vehicle", {}) if isinstance(scenario.get("vehicle"), dict) else {}
    guidance = scenario.get("guidance", {}) if isinstance(scenario.get("guidance"), dict) else {}
    initial = scenario.get("initial", {}) if isinstance(scenario.get("initial"), dict) else {}
    euler = initial.get("euler_deg", [0.0, 0.0, 0.0])
    return {
        "run": run_index,
        "mass_kg": _first_number(vehicle.get("mass_kg"), default=math.nan),
        "throttle": _first_number(guidance.get("throttle"), default=math.nan),
        "pitch_initial_deg": _list_number(euler, 1),
        "wind_x_mps": _list_number(steady, 0),
        "wind_y_mps": _list_number(steady, 1),
        "wind_z_mps": _list_number(steady, 2),
    }


def write_trade_space_artifacts(
    out_dir: str | Path,
    samples: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    study_name: str,
    objectives: list[dict[str, Any]] | None = None,
    constraints: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
    run_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    objectives = objectives or DEFAULT_OBJECTIVES
    constraints = constraints or {"require_success": False}
    ranked = core.score_designs(results, objectives=objectives, constraints=constraints)
    feasible = [row for row in ranked if row.get("feasible")]
    front = core.pareto_front(feasible, objectives=objectives)
    sensitivity = core.sensitivity_table(samples, results)
    reliability = core.reliability_summary(results)
    uq = core.uq_summary(results, metric=_preferred_metric(results))
    surrogate: dict[str, Any] | None
    optimization_rows: list[dict[str, Any]]
    try:
        surrogate = core.fit_surrogate_model(samples, results, metric=_preferred_metric(results))
        optimization_rows = core.optimize_from_surrogate(surrogate, samples, candidates=120)
    except ValueError:
        surrogate = None
        optimization_rows = []

    write_csv(out / "samples.csv", samples)
    write_csv(out / "results.csv", results)
    write_csv(out / "design_ranking.csv", ranked)
    write_csv(out / "pareto.csv", front)
    write_csv(out / "sensitivity.csv", sensitivity)
    write_csv(out / "optimization_results.csv", optimization_rows)
    write_json(out / "reliability_summary.json", reliability)
    write_json(out / "uq_summary.json", uq)
    if surrogate is not None:
        write_json(out / "surrogate.json", surrogate)
    manifest = {
        "schema": "aerosim6dof.trade_space.v1",
        "study_name": study_name,
        "generated_at_utc": _utc_now(),
        "runs": len(results),
        "source": source or {},
        "objectives": objectives,
        "constraints": constraints,
        "run_records": run_records or [],
    }
    write_json(out / "manifest.json", manifest)
    write_trade_plots(out, results, ranked)
    summary = {
        "schema": "aerosim6dof.trade_space.summary.v1",
        "study_name": study_name,
        "runs": len(results),
        "successes": reliability["successes"],
        "success_probability": reliability["success_probability"],
        "pareto_rows": len(front),
        "best_design": ranked[0] if ranked else {},
        "ranked_preview": ranked[:24],
        "pareto_preview": front[:24],
        "sensitivity_preview": sensitivity[:16],
        "top_driver": sensitivity[0] if sensitivity else {},
        "reliability": reliability,
        "uq": uq,
        "surrogate": {"available": surrogate is not None, "metrics": surrogate.get("train_metrics", {}) if surrogate else {}},
        "optimization": {"candidates": len(optimization_rows), "best": optimization_rows[0] if optimization_rows else {}},
        "artifacts": [
            "samples.csv",
            "results.csv",
            "design_ranking.csv",
            "pareto.csv",
            "sensitivity.csv",
            "reliability_summary.json",
            "uq_summary.json",
            "surrogate.json" if surrogate else "",
            "optimization_results.csv",
            "trade_space_report.html",
            "plots/miss_vs_qbar.svg",
            "plots/ranking.svg",
        ],
    }
    summary["artifacts"] = [item for item in summary["artifacts"] if item]
    write_json(out / "trade_space_summary.json", summary)
    write_trade_space_report(out, summary, ranked, front, sensitivity)
    return summary


def write_trade_plots(out: Path, results: list[dict[str, Any]], ranked: list[dict[str, Any]]) -> None:
    plot_rows = [
        {
            "time_s": row.get("max_qbar_pa"),
            "miss_distance_m": row.get("miss_distance_m"),
            "max_load_factor_g": row.get("max_load_factor_g"),
        }
        for row in results
    ]
    write_xy_plot(out / "plots" / "miss_vs_qbar.svg", plot_rows, "time_s", ["miss_distance_m"], "Trade: miss distance vs qbar", "max_qbar_pa", "miss_distance_m")
    ranking_rows = [{"time_s": index, "percentile_score": row.get("percentile_score")} for index, row in enumerate(ranked)]
    write_xy_plot(out / "plots" / "ranking.svg", ranking_rows, "time_s", ["percentile_score"], "Design ranking", "rank", "score")


def write_trade_space_report(
    out: str | Path,
    summary: dict[str, Any],
    ranked: list[dict[str, Any]],
    front: list[dict[str, Any]],
    sensitivity: list[dict[str, Any]],
    *,
    title: str = "Trade Space Report",
) -> Path:
    output = Path(out)
    output.mkdir(parents=True, exist_ok=True)
    best = summary.get("best_design", {}) if isinstance(summary.get("best_design"), dict) else {}
    if "studies" in summary:
        rows_html = "".join(
            f"<tr><td>{_html(row.get('study'))}</td><td>{_html(row.get('runs'))}</td><td>{_html(row.get('success_probability'))}</td><td>{_html(row.get('pareto_rows'))}</td></tr>"
            for row in summary.get("studies", [])
        )
        body = f"<h2>Campaign Studies</h2><table><tr><th>Study</th><th>Runs</th><th>Success p</th><th>Pareto</th></tr>{rows_html}</table>"
    else:
        top_ranked = "".join(
            f"<tr><td>{_html(row.get('run'))}</td><td>{_html(row.get('scenario'))}</td><td>{_fmt(row.get('miss_distance_m'))}</td><td>{_fmt(row.get('max_qbar_pa'))}</td><td>{_fmt(row.get('percentile_score'))}</td></tr>"
            for row in ranked[:12]
        )
        top_sensitivity = "".join(
            f"<tr><td>{_html(row.get('parameter'))}</td><td>{_html(row.get('metric'))}</td><td>{_fmt(row.get('correlation'))}</td></tr>"
            for row in sensitivity[:10]
        )
        body = f"""
        <section class="facts">
          <div><span>Runs</span><strong>{_html(summary.get('runs'))}</strong></div>
          <div><span>Success probability</span><strong>{_fmt(summary.get('success_probability'))}</strong></div>
          <div><span>Pareto rows</span><strong>{_html(summary.get('pareto_rows'))}</strong></div>
          <div><span>Best scenario</span><strong>{_html(best.get('scenario'))}</strong></div>
        </section>
        <h2>Ranked Designs</h2>
        <table><tr><th>Run</th><th>Scenario</th><th>Miss m</th><th>Qbar Pa</th><th>Score</th></tr>{top_ranked}</table>
        <h2>Top Sensitivities</h2>
        <table><tr><th>Parameter</th><th>Metric</th><th>Correlation</th></tr>{top_sensitivity}</table>
        <h2>Pareto Count</h2><p>{len(front)} feasible non-dominated designs.</p>
        """
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{_html(title)}</title>
  <style>
    body {{ margin: 0; padding: 32px; background: #101018; color: #f3f3f8; font: 14px/1.5 Inter, Arial, sans-serif; }}
    h1 {{ font-size: 34px; font-weight: 500; margin: 0 0 8px; }}
    h2 {{ margin-top: 28px; font-size: 18px; letter-spacing: .08em; text-transform: uppercase; color: #b9bac8; }}
    p {{ color: #c8c9d4; }}
    .facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1px; border: 1px solid #383948; margin: 28px 0; }}
    .facts div {{ padding: 18px; background: #171822; }}
    .facts span {{ display:block; color:#9ea0af; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
    .facts strong {{ display:block; margin-top:8px; font-size:22px; font-weight:500; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; border: 1px solid #383948; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #30313d; text-align: left; overflow-wrap: anywhere; }}
    th {{ color: #b9bac8; text-transform: uppercase; letter-spacing: .08em; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>{_html(title)}</h1>
  <p>Generated from AeroLab 6DOF outputs. The simulator remains the source of truth; this report ranks and explains the resulting design space.</p>
  {body}
</body>
</html>
"""
    path = output / "trade_space_report.html"
    path.write_text(html, encoding="utf-8")
    return path


def _design_cases(
    scenario: Scenario,
    *,
    samples: int,
    seed: int,
    parameters: dict[str, list[Any]] | None,
    dispersions: dict[str, float] | None,
) -> list[dict[str, Any]]:
    samples = max(1, min(int(samples), 36))
    cases: list[dict[str, Any]] = []
    if parameters:
        for index, sample in enumerate(core.grid_cases(parameters, samples)):
            patch: dict[str, Any] = {}
            for key, value in sample.items():
                _set_dotted_from_base(scenario.raw, patch, key, value)
            cases.append({"seed": seed + index, "sample": sample, "patch": patch})
        return cases
    rng = np.random.default_rng(seed)
    dispersions = dispersions or {"vehicle.mass_kg": 0.25, "guidance.throttle": 0.04, "wind.steady_mps.0": 0.25}
    base = scenario.raw
    for index in range(samples):
        patch: dict[str, Any] = {"sensors": {"seed": seed + index}}
        sample: dict[str, Any] = {}
        for dotted, sigma in dispersions.items():
            nominal = _get_dotted(base, dotted, default=0.0)
            if not isinstance(nominal, (int, float)):
                continue
            value = float(nominal) + float(rng.normal(0.0, sigma))
            if dotted.endswith("throttle"):
                value = float(np.clip(value, 0.0, 1.0))
            if dotted.endswith("mass_kg"):
                value = max(0.1, value)
            _set_dotted_from_base(base, patch, dotted, value)
            sample[dotted.replace(".", "_")] = value
        cases.append({"seed": seed + index, "sample": sample, "patch": patch})
    return cases


def _set_dotted_from_base(base: dict[str, Any], target: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    if parts and parts[-1].isdigit():
        parent_path = ".".join(parts[:-1])
        existing = _get_dotted(base, parent_path, default=[])
        parent = list(existing) if isinstance(existing, list) else []
        index = int(parts[-1])
        while len(parent) <= index:
            parent.append(0.0)
        parent[index] = value
        _set_dotted(target, parent_path, parent)
        return
    _set_dotted(target, dotted, value)


def _set_dotted(target: dict[str, Any], dotted: str, value: Any) -> None:
    current: Any = target
    parts = dotted.split(".")
    for index, part in enumerate(parts[:-1]):
        if part.isdigit():
            item_index = int(part)
            if not isinstance(current, list):
                return
            while len(current) <= item_index:
                current.append({})
            current = current[item_index]
        else:
            if not isinstance(current, dict):
                return
            next_part = parts[index + 1]
            current = current.setdefault(part, [] if next_part.isdigit() else {})
    last = parts[-1]
    if last.isdigit() and isinstance(current, list):
        index = int(last)
        while len(current) <= index:
            current.append(None)
        current[index] = value
    elif isinstance(current, dict):
        current[last] = value


def _get_dotted(source: dict[str, Any], dotted: str, default: Any = None) -> Any:
    current: Any = source
    for part in dotted.split("."):
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if 0 <= index < len(current) else default
        elif isinstance(current, dict):
            current = current.get(part, default)
        else:
            return default
    return current


def _classify_success(summary: dict[str, Any], events: Any, miss_distance: float, max_qbar: float, max_load: float) -> tuple[bool, str]:
    event_types = {str(event.get("type", "")).lower() for event in events if isinstance(event, dict)}
    if any("impact" in event_type or "ground" in event_type for event_type in event_types):
        return False, "ground_contact"
    if any("qbar" in event_type for event_type in event_types):
        return False, "qbar_limit"
    if any("load" in event_type for event_type in event_types):
        return False, "load_limit"
    final = summary.get("final", {}) if isinstance(summary.get("final"), dict) else {}
    if core.as_float(final.get("altitude_agl_m"), core.as_float(final.get("altitude_m"), 1.0)) <= 0.0:
        return False, "terrain"
    if math.isfinite(miss_distance):
        return miss_distance <= 250.0, "none" if miss_distance <= 250.0 else "miss_distance"
    if max_qbar > 90000.0:
        return False, "qbar_limit"
    if max_load > 15.0:
        return False, "load_limit"
    return True, "none"


def _robustness_margin(summary: dict[str, Any], miss_distance: float, max_qbar: float, max_load: float) -> float:
    margins = [90000.0 - max_qbar, (15.0 - max_load) * 1000.0]
    final = summary.get("final", {}) if isinstance(summary.get("final"), dict) else {}
    altitude = _first_number(final.get("altitude_agl_m"), final.get("altitude_m"), default=math.nan)
    if math.isfinite(altitude):
        margins.append(altitude * 5.0)
    if math.isfinite(miss_distance):
        margins.append((250.0 - miss_distance) * 10.0)
    return float(min(margins)) if margins else math.nan


def _preferred_metric(results: list[dict[str, Any]]) -> str:
    for metric in ["miss_distance_m", "final_altitude_m", "max_qbar_pa"]:
        values = [core.as_float(row.get(metric)) for row in results]
        if any(math.isfinite(value) for value in values):
            return metric
    return "max_qbar_pa"


def _integrate(rows: list[dict[str, Any]], key: str) -> float:
    total = 0.0
    previous_time: float | None = None
    previous_value: float | None = None
    for row in rows:
        time_s = core.as_float(row.get("time_s"))
        value = core.as_float(row.get(key))
        if not math.isfinite(time_s) or not math.isfinite(value):
            continue
        if previous_time is not None and previous_value is not None:
            total += 0.5 * (value + previous_value) * max(0.0, time_s - previous_time)
        previous_time = time_s
        previous_value = value
    return total


def _max(rows: list[dict[str, Any]], key: str) -> float:
    values = [core.as_float(row.get(key)) for row in rows]
    finite = [value for value in values if math.isfinite(value)]
    return max(finite) if finite else math.nan


def _first_number(*values: Any, default: float = math.nan) -> float:
    for value in values:
        number = core.as_float(value)
        if math.isfinite(number):
            return number
    return default


def _list_number(values: Any, index: int) -> float:
    if isinstance(values, list) and len(values) > index:
        return _first_number(values[index], default=math.nan)
    return math.nan


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fmt(value: Any) -> str:
    number = core.as_float(value)
    if math.isfinite(number):
        return f"{number:.4g}"
    return _html(value)


def _html(value: Any) -> str:
    import html

    return html.escape("" if value is None else str(value))


ROW_DEFAULT_OBJECTIVES: dict[str, str] = {
    "final_altitude_m": "max",
    "max_qbar_pa": "min",
    "max_load_factor_g": "min",
}
ROW_DEFAULT_METRICS = (
    "final_altitude_m",
    "final_speed_mps",
    "max_altitude_m",
    "max_speed_mps",
    "max_qbar_pa",
    "max_load_factor_g",
    "min_target_distance_m",
    "min_target_range_m",
    "min_interceptor_range_m",
    "event_count",
)
_ADAPTER_AGGREGATES = (
    "campaign_summary.json",
    "monte_carlo_summary.json",
    "fault_campaign_summary.json",
    "batch_summary.json",
)
_ADAPTER_INDEXES = (
    "campaign_index.csv",
    "monte_carlo_index.csv",
    "fault_campaign_index.csv",
    "batch_index.csv",
)
_ADAPTER_OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


def run(
    source: str | Path | Mapping[str, Any],
    *,
    design: Mapping[str, Any] | None = None,
    design_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Adapt one existing run directory or summary mapping to a trade-study row."""

    base_dir: Path | None = None
    if isinstance(source, (str, Path)):
        path = Path(source)
        summary_path = path / "summary.json" if path.is_dir() else path
        if summary_path.name != "summary.json":
            raise ValueError(f"{summary_path}: expected summary.json or a run directory")
        summary = _adapter_read_json(summary_path)
        base_dir = summary_path.parent
    else:
        summary = dict(source)
    row = _adapter_summary_to_row(summary, base_dir=base_dir, design=design)
    if design_paths and base_dir is not None:
        scenario_path = base_dir / "scenario_resolved.json"
        if scenario_path.exists():
            scenario = _adapter_read_json(scenario_path)
            for dotted in design_paths:
                value = _adapter_get_dotted(scenario, dotted)
                if value is not None:
                    row[f"param_{dotted}"] = _adapter_clean(value)
    return row


def sweep(
    source: str | Path | Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    design_paths: Sequence[str] | None = None,
    max_rows: int = 10_000,
) -> list[dict[str, Any]]:
    """Adapt sweep, Monte Carlo, fault, batch, CSV, or explicit rows to trade rows."""

    return [dict(row) for row in _adapter_rows(source, design_paths=design_paths, max_rows=max_rows)]


def pareto(
    rows: str | Path | Sequence[Mapping[str, Any]],
    objectives: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return non-dominated rows for metric directions like ``{'metric': 'min'}``."""

    data = _adapter_rows(rows)
    objective_map = _adapter_objectives(objectives or ROW_DEFAULT_OBJECTIVES)
    candidates = [row for row in data if all(_adapter_number(row.get(metric)) is not None for metric in objective_map)]
    front: list[dict[str, Any]] = []
    for index, row in enumerate(candidates):
        if any(_adapter_dominates(other, row, objective_map) for other_index, other in enumerate(candidates) if other_index != index):
            continue
        item = dict(row)
        item["pareto_objectives"] = dict(objective_map)
        front.append(item)
    front.sort(key=lambda row: tuple(_adapter_objective_sort(row, metric, sense) for metric, sense in objective_map.items()))
    for index, row in enumerate(front):
        row["pareto_index"] = index
    return front


def reliability(
    rows: str | Path | Sequence[Mapping[str, Any]],
    requirements: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate pass/fail reliability against explicit safe metric requirements."""

    data = _adapter_rows(rows)
    checks = _adapter_requirements(requirements or {})
    evaluated: list[dict[str, Any]] = []
    pass_count = 0
    for row in data:
        passed, failed = _adapter_row_passes(row, checks)
        pass_count += 1 if passed else 0
        item = dict(row)
        item["passed"] = passed
        item["failed_requirements"] = failed
        evaluated.append(item)
    count = len(evaluated)
    return {
        "count": count,
        "pass_count": pass_count,
        "failure_count": count - pass_count,
        "reliability": float(pass_count / count) if count else None,
        "requirements": _adapter_requirements_output(checks),
        "rows": evaluated,
    }


def uq(
    rows: str | Path | Sequence[Mapping[str, Any]],
    metrics: Sequence[str] | None = None,
    percentiles: Sequence[float] = (5.0, 50.0, 95.0),
) -> dict[str, Any]:
    """Compute uncertainty/statistical summaries for numeric trade row metrics."""

    data = _adapter_rows(rows)
    stats: dict[str, Any] = {}
    for metric in list(metrics or _adapter_default_metrics(data)):
        values = [_adapter_number(row.get(metric)) for row in data]
        finite = np.asarray([value for value in values if value is not None], dtype=float)
        if finite.size == 0:
            continue
        entry: dict[str, Any] = {
            "count": int(finite.size),
            "mean": float(np.mean(finite)),
            "std": float(np.std(finite)),
            "min": float(np.min(finite)),
            "max": float(np.max(finite)),
        }
        for percentile in percentiles:
            entry[f"p{_adapter_percentile_label(percentile)}"] = float(np.percentile(finite, percentile))
        stats[metric] = entry
    return {"count": len(data), "metrics": stats}


def sensitivity(
    rows: str | Path | Sequence[Mapping[str, Any]],
    *,
    parameters: Sequence[str] | None = None,
    metrics: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compute simple Pearson correlation and slope sensitivities."""

    data = _adapter_rows(rows)
    entries: list[dict[str, Any]] = []
    for parameter in list(parameters or _adapter_parameter_keys(data)):
        for metric in list(metrics or _adapter_default_metrics(data)):
            pairs = _adapter_pairs(data, parameter, metric)
            if len(pairs) < 2:
                continue
            x = np.asarray([pair[0] for pair in pairs], dtype=float)
            y = np.asarray([pair[1] for pair in pairs], dtype=float)
            if float(np.ptp(x)) == 0.0 or float(np.ptp(y)) == 0.0:
                corr: float | None = None
                slope: float | None = None
            else:
                corr = float(np.corrcoef(x, y)[0, 1])
                slope = float(np.polyfit(x, y, 1)[0])
            entries.append(
                {
                    "parameter": parameter,
                    "metric": metric,
                    "sample_count": len(pairs),
                    "correlation": corr,
                    "abs_correlation": abs(corr) if corr is not None else None,
                    "slope": slope,
                    "parameter_min": float(np.min(x)),
                    "parameter_max": float(np.max(x)),
                    "metric_min": float(np.min(y)),
                    "metric_max": float(np.max(y)),
                }
            )
    entries.sort(key=lambda item: item["abs_correlation"] if item["abs_correlation"] is not None else -1.0, reverse=True)
    return {"count": len(entries), "sensitivities": entries}


def surrogate(
    rows: str | Path | Sequence[Mapping[str, Any]],
    target: str,
    *,
    features: Sequence[str] | None = None,
    degree: int = 1,
) -> dict[str, Any]:
    """Fit a conservative linear surrogate over numeric trade rows."""

    if degree != 1:
        raise ValueError("only degree=1 linear surrogates are supported")
    data = _adapter_rows(rows)
    feature_names = list(features or _adapter_parameter_keys(data))
    if not feature_names:
        raise ValueError("surrogate requires at least one numeric feature")
    x_rows: list[list[float]] = []
    y_values: list[float] = []
    training_rows: list[dict[str, Any]] = []
    for row in data:
        y = _adapter_number(row.get(target))
        x = [_adapter_number(row.get(feature)) for feature in feature_names]
        if y is None or any(value is None for value in x):
            continue
        x_rows.append([1.0, *[float(value) for value in x if value is not None]])
        y_values.append(y)
        training_rows.append(dict(row))
    if len(x_rows) < 2:
        raise ValueError("surrogate requires at least two complete rows")
    x_mat = np.asarray(x_rows, dtype=float)
    y_vec = np.asarray(y_values, dtype=float)
    coeffs, *_ = np.linalg.lstsq(x_mat, y_vec, rcond=None)
    predicted = x_mat @ coeffs
    residuals = y_vec - predicted
    total_var = float(np.sum((y_vec - np.mean(y_vec)) ** 2))
    residual_var = float(np.sum(residuals**2))
    return {
        "kind": "linear",
        "target": target,
        "features": feature_names,
        "sample_count": len(y_values),
        "intercept": float(coeffs[0]),
        "coefficients": {feature: float(coeffs[index + 1]) for index, feature in enumerate(feature_names)},
        "rmse": float(np.sqrt(np.mean(residuals**2))),
        "r2": float(1.0 - residual_var / total_var) if total_var > 0.0 else None,
        "training_rows": training_rows,
    }


def predict_surrogate(model: Mapping[str, Any], design: Mapping[str, Any]) -> float:
    """Evaluate a model returned by :func:`surrogate`."""

    if model.get("kind") != "linear":
        raise ValueError("only linear surrogate models are supported")
    coefficients = model.get("coefficients", {})
    if not isinstance(coefficients, Mapping):
        raise ValueError("surrogate model coefficients must be a mapping")
    value = float(model.get("intercept", 0.0))
    for feature in model.get("features", []):
        x = _adapter_number(design.get(feature))
        if x is None:
            raise ValueError(f"design value for feature {feature} must be finite")
        value += float(coefficients.get(feature, 0.0)) * x
    return float(value)


def optimize(
    rows: str | Path | Sequence[Mapping[str, Any]],
    objective: str,
    *,
    direction: str = "max",
    requirements: Mapping[str, Any] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Rank existing rows by one objective after applying requirements."""

    data = _adapter_rows(rows)
    sense = _adapter_direction(direction)
    checks = _adapter_requirements(requirements or {})
    candidates: list[dict[str, Any]] = []
    infeasible = 0
    for row in data:
        passed, failed = _adapter_row_passes(row, checks)
        value = _adapter_number(row.get(objective))
        item = dict(row)
        item["objective"] = objective
        item["objective_value"] = value
        item["failed_requirements"] = failed
        if passed and value is not None:
            candidates.append(item)
        else:
            infeasible += 1
    candidates.sort(key=lambda row: float(row["objective_value"]), reverse=sense == "max")
    ranked = candidates[: max(0, int(limit))]
    for index, row in enumerate(ranked):
        row["rank"] = index + 1
    return {
        "objective": objective,
        "direction": sense,
        "evaluated_count": len(data),
        "feasible_count": len(candidates),
        "infeasible_count": infeasible,
        "best": ranked[0] if ranked else None,
        "ranked": ranked,
        "requirements": _adapter_requirements_output(checks),
    }


def campaign(
    source: str | Path | Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    objectives: Mapping[str, str] | None = None,
    requirements: Mapping[str, Any] | None = None,
    metrics: Sequence[str] | None = None,
    objective: str | None = None,
    direction: str = "max",
    design_paths: Sequence[str] | None = None,
    max_rows: int = 10_000,
) -> dict[str, Any]:
    """Build a read-only trade-space analysis bundle from existing artifacts."""

    rows = sweep(source, design_paths=design_paths, max_rows=max_rows)
    metric_names = list(metrics or _adapter_default_metrics(rows))
    objective_map = _adapter_objectives(objectives or ROW_DEFAULT_OBJECTIVES)
    objective_name = objective or next(iter(objective_map))
    return {
        "row_count": len(rows),
        "rows": rows,
        "pareto": pareto(rows, objective_map),
        "reliability": reliability(rows, requirements),
        "uq": uq(rows, metric_names),
        "sensitivity": sensitivity(rows, metrics=metric_names),
        "optimization": optimize(rows, objective_name, direction=direction, requirements=requirements),
    }


def uncertainty_quantification(
    rows: str | Path | Sequence[Mapping[str, Any]],
    metrics: Sequence[str] | None = None,
    percentiles: Sequence[float] = (5.0, 50.0, 95.0),
) -> dict[str, Any]:
    return uq(rows, metrics=metrics, percentiles=percentiles)


def load_trade_rows(
    source: str | Path | Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    design_paths: Sequence[str] | None = None,
    max_rows: int = 10_000,
) -> list[dict[str, Any]]:
    return sweep(source, design_paths=design_paths, max_rows=max_rows)


def _adapter_rows(
    source: str | Path | Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    design_paths: Sequence[str] | None = None,
    max_rows: int = 10_000,
) -> list[dict[str, Any]]:
    if isinstance(source, (str, Path)):
        rows = _adapter_rows_from_path(Path(source), design_paths=design_paths)
    elif isinstance(source, Mapping):
        rows = _adapter_rows_from_mapping(source)
    else:
        rows = [_adapter_mapping_to_row(row) for row in source]
    if len(rows) > max_rows:
        raise ValueError(f"trade-space input has {len(rows)} rows, above max_rows={max_rows}")
    return rows


def _adapter_rows_from_path(path: Path, *, design_paths: Sequence[str] | None = None) -> list[dict[str, Any]]:
    if path.is_dir():
        if (path / "summary.json").exists():
            return [run(path, design_paths=design_paths)]
        for filename in _ADAPTER_AGGREGATES:
            candidate = path / filename
            if candidate.exists():
                return _adapter_rows_from_mapping(_adapter_read_json(candidate), base_dir=path)
        for filename in _ADAPTER_INDEXES:
            candidate = path / filename
            if candidate.exists():
                return [_adapter_mapping_to_row(row) for row in _adapter_read_csv(candidate)]
        raise ValueError(f"{path}: no recognized run or campaign artifacts found")
    if path.suffix.lower() == ".csv":
        return [_adapter_mapping_to_row(row) for row in _adapter_read_csv(path)]
    payload = _adapter_read_json(path)
    if path.name == "summary.json":
        return [run(path)]
    return _adapter_rows_from_mapping(payload, base_dir=path.parent)


def _adapter_rows_from_mapping(payload: Mapping[str, Any], base_dir: Path | None = None) -> list[dict[str, Any]]:
    runs = payload.get("runs")
    if isinstance(runs, Sequence) and not isinstance(runs, (str, bytes)):
        source_kind = str(payload.get("kind", _adapter_infer_kind(payload)))
        return [
            _adapter_summary_to_row(item, base_dir=base_dir, source_kind=source_kind)
            for item in runs
            if isinstance(item, Mapping)
        ]
    return [_adapter_summary_to_row(payload, base_dir=base_dir)]


def _adapter_summary_to_row(
    summary: Mapping[str, Any],
    *,
    base_dir: Path | None = None,
    design: Mapping[str, Any] | None = None,
    source_kind: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {"scenario": summary.get("scenario", summary.get("name", ""))}
    row["run_id"] = str(summary.get("run_id", row["scenario"]))
    if source_kind:
        row["source_kind"] = source_kind
    if summary.get("run_dir"):
        row["run_dir"] = str(summary["run_dir"])
    elif base_dir is not None and (base_dir / "summary.json").exists():
        row["run_dir"] = str(base_dir)
    for key, value in summary.items():
        if key in {"final", "parameters", "dispersions", "runs"}:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            row[str(key)] = _adapter_clean(value)
    final = summary.get("final", {})
    if isinstance(final, Mapping):
        for key, value in final.items():
            row[f"final_{key}"] = _adapter_clean(value)
    for namespace, prefix in (("parameters", "param_"), ("dispersions", "dispersion_")):
        values = summary.get(namespace, {})
        if isinstance(values, Mapping):
            for key, value in values.items():
                row[f"{prefix}{key}"] = _adapter_clean(value)
    if design:
        for key, value in design.items():
            row[f"param_{key}"] = _adapter_clean(value)
    return _adapter_mapping_to_row(row)


def _adapter_mapping_to_row(item: Mapping[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, value in item.items():
        normalized = str(key)
        if normalized.startswith("final.") or normalized.startswith("param."):
            normalized = normalized.replace(".", "_", 1)
        row[normalized] = _adapter_clean(value)
    return row


def _adapter_read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return payload


def _adapter_read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _adapter_clean(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        try:
            number = float(text)
        except ValueError:
            return value
        return number if math.isfinite(number) else None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _adapter_objectives(objectives: Mapping[str, str]) -> dict[str, str]:
    normalized = {str(metric): _adapter_direction(sense) for metric, sense in objectives.items()}
    if not normalized:
        raise ValueError("at least one objective is required")
    return normalized


def _adapter_direction(direction: str) -> str:
    text = str(direction).strip().lower()
    text = {"maximize": "max", "maximum": "max", "minimize": "min", "minimum": "min"}.get(text, text)
    if text not in {"min", "max"}:
        raise ValueError("objective direction must be 'min' or 'max'")
    return text


def _adapter_dominates(a: Mapping[str, Any], b: Mapping[str, Any], objectives: Mapping[str, str]) -> bool:
    better_once = False
    for metric, sense in objectives.items():
        av = _adapter_number(a.get(metric))
        bv = _adapter_number(b.get(metric))
        if av is None or bv is None:
            return False
        if sense == "max":
            if av < bv:
                return False
            better_once = better_once or av > bv
        else:
            if av > bv:
                return False
            better_once = better_once or av < bv
    return better_once


def _adapter_objective_sort(row: Mapping[str, Any], metric: str, sense: str) -> float:
    value = _adapter_number(row.get(metric))
    if value is None:
        return float("inf")
    return -value if sense == "max" else value


def _adapter_requirements(requirements: Mapping[str, Any]) -> dict[str, tuple[str, float]]:
    return {str(metric): _adapter_requirement(rule) for metric, rule in requirements.items()}


def _adapter_requirement(rule: Any) -> tuple[str, float]:
    if isinstance(rule, (int, float)):
        return ">=", float(rule)
    if isinstance(rule, (list, tuple)) and len(rule) == 2:
        op, value = str(rule[0]).strip(), _adapter_number(rule[1])
        if op not in _ADAPTER_OPS or value is None:
            raise ValueError("invalid requirement")
        return op, value
    text = str(rule).strip()
    for op in ("<=", ">=", "!=", "==", "<", ">"):
        if text.startswith(op):
            value = _adapter_number(text[len(op) :].strip())
            if value is None:
                raise ValueError("requirement threshold must be finite")
            return op, value
    raise ValueError("requirements must be numbers, (operator, value) pairs, or strings like '<=50000'")


def _adapter_row_passes(row: Mapping[str, Any], checks: Mapping[str, tuple[str, float]]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    for metric, (op, threshold) in checks.items():
        value = _adapter_number(row.get(metric))
        if value is None or not _ADAPTER_OPS[op](value, threshold):
            failed.append(f"{metric} {op} {threshold:g}")
    if not checks and isinstance(row.get("success", row.get("passed")), bool):
        passed = bool(row.get("success", row.get("passed")))
        return passed, [] if passed else ["success flag is false"]
    return not failed, failed


def _adapter_requirements_output(checks: Mapping[str, tuple[str, float]]) -> dict[str, str]:
    return {metric: f"{op}{threshold:g}" for metric, (op, threshold) in checks.items()}


def _adapter_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _adapter_default_metrics(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    found = [metric for metric in ROW_DEFAULT_METRICS if any(_adapter_number(row.get(metric)) is not None for row in rows)]
    for row in rows:
        for key, value in row.items():
            if key in found or key in {"scenario", "run_id", "run_dir", "label", "kind", "source_kind"}:
                continue
            if key.startswith("param_") or key.startswith("dispersion_"):
                continue
            if _adapter_number(value) is not None:
                found.append(key)
    return found


def _adapter_parameter_keys(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    keys: list[str] = []
    for row in rows:
        for key, value in row.items():
            if (key.startswith("param_") or key.startswith("dispersion_")) and key not in keys and _adapter_number(value) is not None:
                keys.append(key)
    return keys


def _adapter_pairs(rows: Sequence[Mapping[str, Any]], x_key: str, y_key: str) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for row in rows:
        x = _adapter_number(row.get(x_key))
        y = _adapter_number(row.get(y_key))
        if x is not None and y is not None:
            pairs.append((x, y))
    return pairs


def _adapter_percentile_label(percentile: float) -> str:
    return str(int(percentile)) if float(percentile).is_integer() else str(percentile).replace(".", "_")


def _adapter_infer_kind(payload: Mapping[str, Any]) -> str:
    if "faults" in payload:
        return "fault_campaign"
    if "parameters" in payload:
        return "sweep"
    if "dispersions" in payload:
        return "monte_carlo"
    return "batch"


def _adapter_get_dotted(mapping: Mapping[str, Any], dotted: str) -> Any:
    current: Any = mapping
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


UQ = uq
