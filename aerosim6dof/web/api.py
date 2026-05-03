"""FastAPI app that exposes existing simulator runs to the browser UI."""

from __future__ import annotations

import json
import math
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from aerosim6dof.analysis.aero import aero_report, aero_sweep, inspect_aero
from aerosim6dof.analysis.alarms import evaluate_run_alarms
from aerosim6dof.analysis.compare import compare_histories
from aerosim6dof.analysis.config_tools import config_diff, generate_scenario, inspect_vehicle
from aerosim6dof.analysis.environment import environment_report
from aerosim6dof.analysis.engagement import engagement_report
from aerosim6dof.analysis.examples_gallery import build_examples_gallery
from aerosim6dof.analysis.missile_engagement_compare import build_missile_engagement_comparison, is_missile_showcase_run
from aerosim6dof.analysis.propulsion import inspect_propulsion, thrust_curve_report
from aerosim6dof.analysis.scenario_validation import summarize_scenario_advisories, validate_scenario_advisories
from aerosim6dof.analysis.scenario_builder import (
    scenario_builder_explanation,
    scenario_builder_recommendations,
    scenario_builder_summary,
    scenario_builder_warnings,
)
from aerosim6dof.analysis.sensors import sensor_report
from aerosim6dof.analysis.stability import linear_model_report, stability_report, trim_sweep
from aerosim6dof.analysis.trade_space import (
    analyze_existing_runs,
    run_trade_space_campaign,
    run_trade_space_study,
    run_trade_space_sweep,
)
from aerosim6dof.config import deep_merge, load_json, load_with_optional_base
from aerosim6dof.estimation.navigation_filter import load_navigation_telemetry_from_run
from aerosim6dof.gnc.trim import simple_trim, write_trim_result
from aerosim6dof.metadata import VERSION
from aerosim6dof.reports.csv_writer import read_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.studio import assemble_report_studio_packet
from aerosim6dof.scenario import Scenario
from aerosim6dof.simulation.campaign import run_sweep_campaign
from aerosim6dof.simulation.fault_campaign import FAULT_LIBRARY, run_fault_campaign
from aerosim6dof.simulation.runner import batch_run, linearize_scenario, monte_carlo_run, report_run, run_scenario
from aerosim6dof.telemetry.metadata import metadata_for_channels

from .progress import cancellation_payload, clear_cancel, is_cancel_requested, progress_from_job_summary, request_cancel
from .storage import delete_layout, get_layout, list_layouts, list_report_metadata, save_layout, save_report_metadata, storage_status
from .models import (
    ActionRequest,
    ActionResult,
    AlarmSummary,
    ArtifactRef,
    ConfigSummary,
    JobSummary,
    RunRequest,
    RunSummary,
    ScenarioDetail,
    ScenarioDraft,
    ScenarioDraftRequest,
    TelemetrySeries,
    ValidateRequest,
)


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "examples"
SCENARIOS_DIR = EXAMPLES_DIR / "scenarios"
VEHICLES_DIR = EXAMPLES_DIR / "vehicles"
ENVIRONMENTS_DIR = EXAMPLES_DIR / "environments"
OUTPUTS_DIR = ROOT / "outputs"
WEB_RUNS_DIR = OUTPUTS_DIR / "web_runs"

router = APIRouter()
EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="aerosim-web")
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
SEED_LOCK = threading.Lock()
SEED_SUITE_STARTED = False
REQUIRED_HISTORY_COLUMNS = {
    "altitude_agl_m",
    "terrain_elevation_m",
    "altitude_agl_rate_mps",
    "ground_contact",
    "impact_speed_mps",
    "target_range_m",
    "closing_speed_mps",
    "interceptor_range_m",
}

CAPABILITIES = [
    {"id": "run", "group": "launch", "label": "Run"},
    {"id": "batch", "group": "campaign", "label": "Batch"},
    {"id": "monte_carlo", "group": "campaign", "label": "Monte Carlo"},
    {"id": "sweep", "group": "campaign", "label": "Sweep"},
    {"id": "fault_campaign", "group": "campaign", "label": "Fault Campaign", "faults": sorted(FAULT_LIBRARY)},
    {"id": "trade_space", "group": "campaign", "label": "Trade Space"},
    {"id": "compare_runs", "group": "analysis", "label": "Compare"},
    {"id": "missile_engagement_comparison", "group": "analysis", "label": "Missile Engagement Comparison"},
    {"id": "report", "group": "analysis", "label": "Report"},
    {"id": "engagement_report", "group": "analysis", "label": "Engagement"},
    {"id": "sensor_report", "group": "analysis", "label": "Sensor Report"},
    {"id": "trim", "group": "engineering", "label": "Trim"},
    {"id": "trim_sweep", "group": "engineering", "label": "Trim Sweep"},
    {"id": "linearize", "group": "engineering", "label": "Linearize"},
    {"id": "stability", "group": "engineering", "label": "Stability"},
    {"id": "linear_model_report", "group": "engineering", "label": "Linear Model"},
    {"id": "inspect_vehicle", "group": "model", "label": "Inspect Vehicle"},
    {"id": "config_diff", "group": "model", "label": "Config Diff"},
    {"id": "generate_scenario", "group": "model", "label": "Generate Scenario"},
    {"id": "inspect_aero", "group": "model", "label": "Inspect Aero"},
    {"id": "aero_sweep", "group": "model", "label": "Aero Sweep"},
    {"id": "aero_report", "group": "model", "label": "Aero Report"},
    {"id": "inspect_propulsion", "group": "model", "label": "Inspect Propulsion"},
    {"id": "thrust_curve_report", "group": "model", "label": "Thrust Report"},
    {"id": "environment_report", "group": "model", "label": "Environment Report"},
]


def create_app() -> FastAPI:
    app = FastAPI(title="AeroSim 6DOF API", version=VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    dist = ROOT / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


@router.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": VERSION}


@router.get("/storage/status")
def get_storage_status() -> dict[str, Any]:
    return _safe_json(storage_status())


@router.get("/storage/layouts")
def get_storage_layouts() -> list[dict[str, Any]]:
    try:
        return _safe_json(list_layouts())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/storage/layouts/{layout_id}")
def get_storage_layout(layout_id: str) -> dict[str, Any]:
    try:
        layout = get_layout(layout_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if layout is None:
        raise HTTPException(status_code=404, detail="layout not found")
    return _safe_json(layout)


@router.post("/storage/layouts/{layout_id}")
def put_storage_layout(layout_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _safe_json(save_layout(layout_id, payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/storage/layouts/{layout_id}")
def remove_storage_layout(layout_id: str) -> dict[str, Any]:
    try:
        deleted = delete_layout(layout_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": layout_id, "deleted": deleted}


@router.get("/storage/reports")
def get_storage_reports() -> list[dict[str, Any]]:
    try:
        return _safe_json(list_report_metadata())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/storage/reports/{report_id}")
def put_storage_report(report_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _safe_json(save_report_metadata(report_id, payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/examples-gallery")
def get_examples_gallery() -> list[dict[str, Any]]:
    return _safe_json(build_examples_gallery(EXAMPLES_DIR))


@router.get("/scenarios")
def list_scenarios() -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        try:
            raw = load_json(path)
            scenario = Scenario.from_file(path)
        except ValueError:
            continue
        scenarios.append(
            {
                "id": path.stem,
                "name": scenario.name,
                "path": _repo_relative(path),
                "duration_s": scenario.duration,
                "dt_s": scenario.dt,
                "integrator": scenario.integrator,
                "vehicle_config": raw.get("vehicle_config"),
                "environment_config": raw.get("environment_config"),
                "guidance_mode": scenario.guidance.get("mode"),
            }
        )
    return scenarios


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetail)
def get_scenario(scenario_id: str) -> ScenarioDetail:
    path = _scenario_path(scenario_id)
    raw = load_json(path)
    scenario = Scenario.from_file(path)
    return ScenarioDetail(
        id=path.stem,
        name=scenario.name,
        path=_repo_relative(path),
        duration_s=scenario.duration,
        dt_s=scenario.dt,
        integrator=scenario.integrator,
        vehicle_config=raw.get("vehicle_config"),
        environment_config=raw.get("environment_config"),
        guidance_mode=scenario.guidance.get("mode"),
        raw=_safe_json(raw),
        resolved=_safe_json(scenario.raw),
    )


@router.post("/scenario-drafts", response_model=ScenarioDraft)
def create_scenario_draft(payload: ScenarioDraftRequest) -> ScenarioDraft:
    name = payload.name or str(payload.scenario.get("name", "browser_scenario"))
    try:
        scenario = _scenario_from_payload(payload.scenario)
    except ValueError as exc:
        return ScenarioDraft(
            id="",
            name=name,
            path="",
            valid=False,
            errors=[str(exc)],
            scenario=_safe_json(payload.scenario),
        )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    draft_dir = WEB_RUNS_DIR / "scenario_drafts"
    draft_path = draft_dir / f"{_run_slug(name)}_{timestamp}.json"
    write_json(draft_path, _safe_json(payload.scenario))
    return ScenarioDraft(
        id=draft_path.stem,
        name=scenario.name,
        path=_repo_relative(draft_path),
        valid=True,
        scenario=_safe_json(payload.scenario),
    )


@router.get("/vehicles", response_model=list[ConfigSummary])
def list_vehicles() -> list[ConfigSummary]:
    return _list_configs(VEHICLES_DIR)


@router.get("/environments", response_model=list[ConfigSummary])
def list_environments() -> list[ConfigSummary]:
    return _list_configs(ENVIRONMENTS_DIR)


@router.get("/capabilities")
def list_capabilities() -> list[dict[str, Any]]:
    return CAPABILITIES


@router.post("/validate")
def validate_scenario(payload: ValidateRequest) -> dict[str, Any]:
    raw_config: dict[str, Any] = {}
    advisory_base = SCENARIOS_DIR
    try:
        if payload.scenario_id:
            path = _scenario_path(payload.scenario_id)
            advisory_base = path.parent
            raw_config = load_json(path)
            scenario = Scenario.from_file(path)
        elif payload.scenario is not None:
            raw_config = payload.scenario
            scenario = _scenario_from_payload(payload.scenario)
        else:
            raise HTTPException(status_code=400, detail="scenario_id or scenario is required")
    except ValueError as exc:
        return {
            "valid": False,
            "errors": [str(exc)],
            **_scenario_builder_advisory(raw_config),
            **_scenario_validation_payload(raw_config, advisory_base),
        }
    validation_payload = _scenario_validation_payload(raw_config, advisory_base)
    return {
        "valid": True,
        "scenario": scenario.name,
        "dt": scenario.dt,
        "duration": scenario.duration,
        "integrator": scenario.integrator,
        **_scenario_builder_advisory(raw_config),
        **validation_payload,
    }


@router.post("/runs", response_model=RunSummary)
def create_run(payload: RunRequest) -> RunSummary:
    scenario_path = _scenario_path(payload.scenario_id)
    try:
        scenario = Scenario.from_file(scenario_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run_slug = _run_slug(payload.run_name or scenario.name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = WEB_RUNS_DIR / f"{run_slug}_{timestamp}"
    try:
        run_scenario(scenario, run_dir)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _build_run_summary(run_dir)


@router.post("/actions/{action}", response_model=ActionResult)
def run_action(action: str, payload: ActionRequest) -> ActionResult:
    params = payload.params
    try:
        result = _execute_action(action, params)
    except HTTPException:
        raise
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/jobs/{action}", response_model=JobSummary)
def create_job(action: str, payload: ActionRequest) -> JobSummary:
    if action not in {item["id"] for item in CAPABILITIES}:
        raise HTTPException(status_code=404, detail=f"unsupported action: {action}")
    job_id = uuid.uuid4().hex[:12]
    now = _utc_now()
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "action": action,
            "status": "queued",
            "message": "queued",
            "progress": 0.0,
            "created_at_utc": now,
            "started_at_utc": None,
            "finished_at_utc": None,
            "events": [{"time_utc": now, "status": "queued", "message": "queued", "progress": 0.0}],
            "result": None,
            "params": _safe_json(dict(payload.params)),
        }
    EXECUTOR.submit(_run_job, job_id, action, dict(payload.params))
    return _job_summary(job_id)


@router.get("/jobs", response_model=list[JobSummary])
def list_jobs(limit: int = Query(30, ge=1, le=100)) -> list[JobSummary]:
    with JOBS_LOCK:
        ids = sorted(JOBS, key=lambda key: JOBS[key]["created_at_utc"], reverse=True)[:limit]
    return [_job_summary(job_id) for job_id in ids]


@router.get("/jobs/{job_id}", response_model=JobSummary)
def get_job(job_id: str) -> JobSummary:
    return _job_summary(job_id)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    job = _job_payload(job_id)
    if job["status"] in {"completed", "failed", "cancelled"}:
        return {"cancel": cancellation_payload(job_id), "job": _job_summary(job_id)}
    state = request_cancel(
        job_id,
        reason=(payload or {}).get("reason"),
        requested_by=(payload or {}).get("requested_by"),
        message=(payload or {}).get("message"),
    )
    if job["status"] == "queued":
        _job_update(job_id, status="cancelled", message="cancelled before start", progress=1.0, finished=True)
    else:
        _job_update(job_id, status=job["status"], message="cancellation requested", progress=float(job.get("progress", 0.0)))
    return {"cancel": state.to_dict(), "job": _job_summary(job_id)}


@router.post("/jobs/{job_id}/retry", response_model=JobSummary)
def retry_job(job_id: str) -> JobSummary:
    job = _job_payload(job_id, public=False)
    if job["status"] not in {"failed", "cancelled"}:
        raise HTTPException(status_code=400, detail="only failed or cancelled jobs can be retried")
    params = job.get("params")
    if not isinstance(params, dict):
        params = {}
    return create_job(str(job["action"]), ActionRequest(params=dict(params)))


@router.get("/jobs/{job_id}/events")
def stream_job_events(job_id: str) -> StreamingResponse:
    _job_summary(job_id)
    return StreamingResponse(_job_event_stream(job_id), media_type="text/event-stream")


@router.get("/jobs/{job_id}/progress")
def get_job_progress(job_id: str) -> dict[str, Any]:
    job = _job_summary(job_id)
    payload = job.model_dump() if hasattr(job, "model_dump") else job.dict()
    return _safe_json(progress_from_job_summary(payload).to_dict())


@router.get("/runs", response_model=list[RunSummary])
def list_runs(limit: int = Query(80, ge=1, le=300)) -> list[RunSummary]:
    run_dirs = _discover_run_dirs()
    run_dirs.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return [_build_run_summary(path) for path in run_dirs[:limit]]


@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(run_id: str) -> RunSummary:
    return _build_run_summary(_run_dir_from_id(run_id))


@router.get("/runs/{run_id}/telemetry", response_model=TelemetrySeries)
def get_telemetry(run_id: str, stride: int = Query(1, ge=1, le=5000)) -> TelemetrySeries:
    run_dir = _run_dir_from_id(run_id)
    datasets: dict[str, list[dict[str, Any]]] = {}
    channels: dict[str, list[str]] = {}
    sample_count = 0
    for name in ("history", "truth", "controls", "sensors", "targets", "interceptors"):
        path = run_dir / f"{name}.csv"
        if not path.exists():
            datasets[name] = []
            channels[name] = []
            continue
        rows = [_clean_row(row) for row in read_csv(path)]
        sample_count = max(sample_count, len(rows))
        datasets[name] = rows[::stride]
        channels[name] = list(rows[0].keys()) if rows else []
    return TelemetrySeries(run_id=run_id, stride=stride, sample_count=sample_count, channels=channels, metadata=metadata_for_channels(channels), **datasets)


@router.get("/runs/{run_id}/alarms", response_model=list[AlarmSummary])
def get_run_alarms(run_id: str) -> list[AlarmSummary]:
    run_dir = _run_dir_from_id(run_id)
    try:
        return [AlarmSummary(**alarm) for alarm in evaluate_run_alarms(run_dir)]
    except Exception:  # pragma: no cover - alarms must not block replay loading
        return []


@router.get("/runs/{run_id}/navigation")
def get_run_navigation(run_id: str, stride: int = Query(3, ge=1, le=5000)) -> dict[str, Any]:
    run_dir = _run_dir_from_id(run_id)
    try:
        payload = load_navigation_telemetry_from_run(run_dir, stride=stride)
    except Exception as exc:  # pragma: no cover - navigation must not break run loading
        payload = {
            "rows": [],
            "channels": [],
            "summary": {"row_count": 0, "stride": stride, "source": "error", "warnings": [str(exc)]},
        }
    channel_keys = [str(item.get("key")) for item in payload.get("channels", []) if isinstance(item, dict) and item.get("key")]
    payload["run_id"] = run_id
    payload["metadata"] = metadata_for_channels({"derived": channel_keys})
    return _safe_json(payload)


@router.get("/runs/{run_id}/report-studio")
def get_report_studio_packet(run_id: str, sections: str | None = Query(default=None)) -> dict[str, Any]:
    run_dir = _run_dir_from_id(run_id)
    section_list = [item.strip() for item in sections.split(",") if item.strip()] if sections else None
    try:
        return _safe_json(
            assemble_report_studio_packet(
                run_dir,
                sections=section_list,
                artifact_base_url=f"/api/artifacts/{run_id}",
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/missile-engagement-comparison")
def get_missile_engagement_comparison(
    run_ids: str | None = Query(default=None),
    max_runs: int = Query(default=4, ge=1, le=8),
    max_samples: int = Query(default=240, ge=20, le=1000),
) -> dict[str, Any]:
    if run_ids:
        ids = [item.strip() for item in run_ids.split(",") if item.strip()]
        if not ids:
            raise HTTPException(status_code=400, detail="run_ids must include at least one run id")
        ids = ids[:max_runs]
        run_dirs = [_run_dir_from_id(run_id) for run_id in ids]
    else:
        run_dirs = _discover_missile_showcase_run_dirs(max_runs=max_runs)
        ids = [_run_id(path) for path in run_dirs]
    return _safe_json(build_missile_engagement_comparison(run_dirs, run_ids=ids, max_samples=max_samples))


@router.get("/artifacts/{run_id}/{artifact_path:path}")
def get_artifact(run_id: str, artifact_path: str) -> FileResponse:
    output_dir = _output_dir_from_id(run_id)
    target = (output_dir / artifact_path).resolve()
    if not _is_within(target, output_dir.resolve()) or not target.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(target)


def _scenario_builder_advisory(config: dict[str, Any]) -> dict[str, Any]:
    """Return optional scenario-builder guidance without blocking validation."""
    if not isinstance(config, dict):
        config = {}
    try:
        return {
            "summary": _safe_json(scenario_builder_summary(config)),
            "warnings": _safe_json(scenario_builder_warnings(config)),
            "explanation": scenario_builder_explanation(config),
            "recommendations": scenario_builder_recommendations(config),
        }
    except Exception:  # pragma: no cover - advisory data must not break validation
        return {"summary": {}, "warnings": [], "explanation": "", "recommendations": []}


def _scenario_validation_payload(config: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    try:
        advisories = validate_scenario_advisories(config, base_dir=base_dir)
        return {
            "advisories": [advisory.to_dict() for advisory in advisories],
            "advisory_summary": summarize_scenario_advisories(advisories),
        }
    except Exception:  # pragma: no cover - advisories must not block validation
        return {"advisories": [], "advisory_summary": summarize_scenario_advisories([])}


def _execute_action(action: str, params: dict[str, Any]) -> ActionResult:
    scenario_id = str(params.get("scenario_id", "nominal_ascent"))
    vehicle_id = str(params.get("vehicle_id", "baseline"))
    environment_id = str(params.get("environment_id", "calm"))
    if action == "run":
        scenario_payload = params.get("scenario")
        scenario = _scenario_from_payload(scenario_payload) if isinstance(scenario_payload, dict) else Scenario.from_file(_scenario_path(scenario_id))
        out = _action_dir("run", str(params.get("run_name", scenario.name)))
        data = run_scenario(scenario, out)
        return _action_result(action, out, data)
    if action == "batch":
        out = _action_dir("batch", "scenario_batch")
        data = batch_run(SCENARIOS_DIR, out)
        return _action_result(action, out, data)
    if action == "monte_carlo":
        scenario = Scenario.from_file(_scenario_path(scenario_id))
        dispersions: dict[str, float] = {}
        mass_sigma = float(params.get("mass_sigma_kg", 0.2))
        wind_sigma = float(params.get("wind_sigma_mps", 0.1))
        if mass_sigma > 0.0:
            dispersions["mass_sigma_kg"] = mass_sigma
        if wind_sigma > 0.0:
            dispersions["wind_sigma_mps"] = wind_sigma
        out = _action_dir("monte_carlo", scenario.name)
        data = monte_carlo_run(
            scenario,
            max(1, min(int(params.get("samples", 5)), 50)),
            out,
            int(params.get("seed", 77)),
            dispersions,
        )
        return _action_result(action, out, data)
    if action == "sweep":
        scenario = Scenario.from_file(_scenario_path(scenario_id))
        parameter = str(params.get("parameter", "guidance.throttle"))
        values = _parse_value_list(params.get("values", "0.82,0.86"))
        out = _action_dir("sweep", f"{scenario.name}_{parameter.split('.')[-1]}")
        data = run_sweep_campaign(scenario, out, {parameter: values}, max_runs=max(1, min(int(params.get("max_runs", 20)), 100)))
        return _action_result(action, out, data)
    if action == "fault_campaign":
        scenario = Scenario.from_file(_scenario_path(scenario_id))
        faults = params.get("faults")
        fault_names = [str(item) for item in faults] if isinstance(faults, list) and faults else None
        out = _action_dir("fault_campaign", scenario.name)
        data = run_fault_campaign(scenario, out, fault_names, max_runs=max(1, min(int(params.get("max_runs", 12)), 50)))
        return _action_result(action, out, data)
    if action == "trade_space":
        mode = str(params.get("mode", "study"))
        out = _action_dir("trade_space", str(params.get("label", scenario_id)))
        if mode == "existing_runs":
            raw_ids = params.get("run_ids")
            if not isinstance(raw_ids, list) or not raw_ids:
                raise ValueError("trade_space existing_runs requires run_ids")
            run_dirs = [_run_dir_from_id(str(run_id)) for run_id in raw_ids[:80]]
            data = analyze_existing_runs(run_dirs, out, study_name=str(params.get("label", "Existing run trade space")))
        elif mode == "sweep":
            scenario = Scenario.from_file(_scenario_path(scenario_id))
            parameter = str(params.get("parameter", "guidance.throttle"))
            values = _parse_value_list(params.get("values", "0.78,0.86,0.94"))
            data = run_trade_space_sweep(scenario, out, parameter=parameter, values=values)
        elif mode == "campaign":
            scenario = Scenario.from_file(_scenario_path(scenario_id))
            data = run_trade_space_campaign(scenario, out, seed=int(params.get("seed", 2026)), samples=max(2, min(int(params.get("samples", 8)), 18)))
        else:
            scenario = Scenario.from_file(_scenario_path(scenario_id))
            parameters = params.get("parameters")
            parameter = params.get("parameter")
            if not isinstance(parameters, dict) and parameter:
                parameters = {str(parameter): _parse_value_list(params.get("values", ""))}
            dispersions = params.get("dispersions")
            if not isinstance(dispersions, dict):
                dispersions = {
                    "vehicle.mass_kg": float(params.get("mass_sigma_kg", 0.2)),
                    "wind.steady_mps.0": float(params.get("wind_sigma_mps", 0.1)),
                    "guidance.throttle": float(params.get("throttle_sigma", 0.02)),
                }
            data = run_trade_space_study(
                scenario,
                out,
                samples=max(1, min(int(params.get("samples", 8)), 36)),
                seed=int(params.get("seed", 2026)),
                parameters=parameters if isinstance(parameters, dict) else None,
                dispersions=dispersions,
            )
        return _action_result(action, out, data)
    if action == "compare_runs":
        run_a = _run_dir_from_id(str(params["run_a_id"]))
        run_b = _run_dir_from_id(str(params["run_b_id"]))
        out = _action_dir("compare", f"{run_a.name}_vs_{run_b.name}")
        data = compare_histories(run_a / "history.csv", run_b / "history.csv", out)
        return _action_result(action, out, data)
    if action == "missile_engagement_comparison":
        raw_ids = params.get("run_ids")
        if isinstance(raw_ids, list) and raw_ids:
            ids = [str(item) for item in raw_ids][:8]
            run_dirs = [_run_dir_from_id(run_id) for run_id in ids]
        else:
            run_dirs = _discover_missile_showcase_run_dirs(max_runs=4)
            ids = [_run_id(path) for path in run_dirs]
        data = build_missile_engagement_comparison(run_dirs, run_ids=ids, max_samples=max(20, min(int(params.get("max_samples", 240)), 1000)))
        return ActionResult(action=action, data=_safe_json(data))
    if action == "report":
        run_dir = _run_dir_from_id(str(params["run_id"]))
        report_path = report_run(run_dir)
        return _action_result(action, run_dir, {"report": str(report_path)})
    if action == "engagement_report":
        run_dir = _run_dir_from_id(str(params["run_id"]))
        data = engagement_report(run_dir)
        return _action_result(action, run_dir, data)
    if action == "sensor_report":
        run_dir = _run_dir_from_id(str(params["run_id"]))
        out = _action_dir("sensor_report", run_dir.name)
        data = sensor_report(run_dir, out)
        return _action_result(action, out, data)
    if action == "trim":
        out = _action_dir("trim", vehicle_id)
        data = simple_trim(load_json(_vehicle_path(vehicle_id)), float(params.get("speed_mps", 120.0)), float(params.get("altitude_m", 1000.0)))
        write_trim_result(data, out)
        return _action_result(action, out, data)
    if action == "trim_sweep":
        out = _action_dir("trim_sweep", vehicle_id)
        data = trim_sweep(_vehicle_path(vehicle_id), out, _float_list(params.get("speeds", "90,120,150")), _float_list(params.get("altitudes", "0,1000")))
        return _action_result(action, out, data)
    if action == "linearize":
        scenario = Scenario.from_file(_scenario_path(scenario_id))
        out = _action_dir("linearize", scenario.name)
        data = linearize_scenario(scenario, float(params.get("time_s", 3.0)), out)
        return _action_result(action, out, data)
    if action == "stability":
        scenario = Scenario.from_file(_scenario_path(scenario_id))
        out = _action_dir("stability", scenario.name)
        linear = out / "linearization"
        linearize_scenario(scenario, float(params.get("time_s", 3.0)), linear)
        data = stability_report(linear / "linearization.json", out)
        return _action_result(action, out, data)
    if action == "linear_model_report":
        scenario = Scenario.from_file(_scenario_path(scenario_id))
        out = _action_dir("linear_model", scenario.name)
        linear = out / "linearization"
        linearize_scenario(scenario, float(params.get("time_s", 3.0)), linear)
        data = linear_model_report(linear / "linearization.json", out)
        return _action_result(action, out, data)
    if action == "inspect_vehicle":
        return ActionResult(action=action, data=_safe_json(inspect_vehicle(_vehicle_path(vehicle_id))))
    if action == "config_diff":
        a_id = str(params.get("vehicle_a_id", "baseline"))
        b_id = str(params.get("vehicle_b_id", "electric_uav"))
        return ActionResult(action=action, data=_safe_json(config_diff(_vehicle_path(a_id), _vehicle_path(b_id))))
    if action == "generate_scenario":
        out = _action_dir("generated_scenario", str(params.get("name", "browser_template")))
        out_path = out / "scenario.json"
        data = generate_scenario(
            out_path,
            str(params.get("name", "browser_template")),
            str(params.get("vehicle_config", "../vehicles/baseline.json")),
            str(params.get("environment_config", "../environments/calm.json")),
            str(params.get("guidance_mode", "pitch_program")),
        )
        return _action_result(action, out, data)
    if action == "inspect_aero":
        return ActionResult(action=action, data=_safe_json(inspect_aero(_vehicle_path(vehicle_id))))
    if action == "aero_sweep":
        out = _action_dir("aero_sweep", vehicle_id)
        data = aero_sweep(_vehicle_path(vehicle_id), out, _float_list(params.get("mach", "")) or None, _float_list(params.get("alpha", "")) or None)
        return _action_result(action, out, data)
    if action == "aero_report":
        out = _action_dir("aero_report", vehicle_id)
        data = aero_report(_vehicle_path(vehicle_id), out)
        return _action_result(action, out, data)
    if action == "inspect_propulsion":
        return ActionResult(action=action, data=_safe_json(inspect_propulsion(_vehicle_path(vehicle_id))))
    if action == "thrust_curve_report":
        out = _action_dir("thrust_report", vehicle_id)
        data = thrust_curve_report(_vehicle_path(vehicle_id), out)
        return _action_result(action, out, data)
    if action == "environment_report":
        out = _action_dir("environment_report", environment_id)
        data = environment_report(_environment_path(environment_id), out)
        return _action_result(action, out, data)
    raise HTTPException(status_code=404, detail=f"unsupported action: {action}")


def _run_job(job_id: str, action: str, params: dict[str, Any]) -> None:
    if is_cancel_requested(job_id):
        _job_update(job_id, status="cancelled", message="cancelled before start", progress=1.0, finished=True)
        clear_cancel(job_id)
        return
    if not _job_update(job_id, status="running", message="preparing inputs", progress=0.12, started=True):
        return
    try:
        if is_cancel_requested(job_id):
            _job_update(job_id, status="cancelled", message="cancelled before execution", progress=1.0, finished=True)
            clear_cancel(job_id)
            return
        _job_update(job_id, status="running", message=_action_stage(action), progress=0.34)
        result = _execute_action(action, params)
        if is_cancel_requested(job_id):
            _job_update(job_id, status="cancelled", message="cancelled after execution request", progress=1.0, finished=True)
            clear_cancel(job_id)
            return
        _job_update(job_id, status="running", message="indexing artifacts", progress=0.86)
    except Exception as exc:  # pragma: no cover - exercised through API behavior
        _job_update(job_id, status="failed", message=str(exc), progress=1.0, finished=True)
        clear_cancel(job_id)
        return
    _job_update(job_id, status="completed", message=result.message or "completed", progress=1.0, finished=True, result=result)
    clear_cancel(job_id)


def _job_update(
    job_id: str,
    *,
    status: str,
    message: str,
    progress: float,
    started: bool = False,
    finished: bool = False,
    result: ActionResult | None = None,
) -> bool:
    now = _utc_now()
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return False
        job.update(status=status, message=message, progress=max(0.0, min(progress, 1.0)))
        if started and not job.get("started_at_utc"):
            job["started_at_utc"] = now
        if finished:
            job["finished_at_utc"] = now
        if result is not None:
            job["result"] = result
        job.setdefault("events", []).append({"time_utc": now, "status": status, "message": message, "progress": job["progress"]})
    return True


def _action_stage(action: str) -> str:
    if action in {"run", "batch", "monte_carlo", "sweep", "fault_campaign"}:
        return "running simulation"
    if action == "trade_space":
        return "building trade space"
    if action in {
        "compare_runs",
        "missile_engagement_comparison",
        "report",
        "engagement_report",
        "sensor_report",
        "aero_report",
        "thrust_curve_report",
        "environment_report",
    }:
        return "building report"
    if action in {"trim", "trim_sweep", "linearize", "stability", "linear_model_report"}:
        return "solving engineering model"
    return "reading model data"


def _job_summary(job_id: str) -> JobSummary:
    payload = _job_payload(job_id, public=True)
    return JobSummary(**payload)


def _job_payload(job_id: str, *, public: bool = True) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        payload = dict(job)
    if public:
        payload.pop("params", None)
    return payload


def _job_event_stream(job_id: str):
    last_event_count = -1
    while True:
        job = _job_summary(job_id)
        event_count = len(job.events)
        if event_count != last_event_count:
            payload = job.model_dump_json() if hasattr(job, "model_dump_json") else job.json()
            yield f"data: {payload}\n\n"
            last_event_count = event_count
        if job.status in {"completed", "failed", "cancelled"}:
            return
        time.sleep(0.2)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _scenario_from_payload(data: dict[str, Any]) -> Scenario:
    materialized = json.loads(json.dumps(data))
    if "vehicle_config" in materialized:
        vehicle_path = _resolve_example_reference(str(materialized["vehicle_config"]), SCENARIOS_DIR)
        materialized["vehicle"] = deep_merge(load_with_optional_base(vehicle_path), materialized.get("vehicle", {}))
    if "environment_config" in materialized:
        environment_path = _resolve_example_reference(str(materialized["environment_config"]), SCENARIOS_DIR)
        environment = deep_merge(load_with_optional_base(environment_path), materialized.get("environment", {}))
        materialized["environment"] = environment
        if "wind" not in materialized and "wind" in environment:
            materialized["wind"] = environment["wind"]
    scenario = Scenario.from_dict(materialized)
    return scenario


def _resolve_example_reference(value: str, base_dir: Path) -> Path:
    path = Path(value)
    candidate = path.resolve() if path.is_absolute() else (base_dir / path).resolve()
    if not _is_within(candidate, EXAMPLES_DIR.resolve()) or not candidate.exists():
        raise ValueError(f"config reference must resolve inside examples/: {value}")
    return candidate


def _list_configs(directory: Path) -> list[ConfigSummary]:
    configs: list[ConfigSummary] = []
    for path in sorted(directory.glob("*.json")):
        name = path.stem
        try:
            data = load_json(path)
            name = str(data.get("name", name))
        except ValueError:
            pass
        configs.append(ConfigSummary(id=path.stem, name=name, path=_repo_relative(path)))
    return configs


def _scenario_path(scenario_id: str) -> Path:
    key = Path(scenario_id).stem
    path = (SCENARIOS_DIR / f"{key}.json").resolve()
    if not _is_within(path, SCENARIOS_DIR.resolve()) or not path.exists():
        raise HTTPException(status_code=404, detail=f"scenario not found: {scenario_id}")
    return path


def _vehicle_path(vehicle_id: str) -> Path:
    key = Path(vehicle_id).stem
    path = (VEHICLES_DIR / f"{key}.json").resolve()
    if not _is_within(path, VEHICLES_DIR.resolve()) or not path.exists():
        raise HTTPException(status_code=404, detail=f"vehicle not found: {vehicle_id}")
    return path


def _environment_path(environment_id: str) -> Path:
    key = Path(environment_id).stem
    path = (ENVIRONMENTS_DIR / f"{key}.json").resolve()
    if not _is_within(path, ENVIRONMENTS_DIR.resolve()) or not path.exists():
        raise HTTPException(status_code=404, detail=f"environment not found: {environment_id}")
    return path


def _discover_run_dirs() -> list[Path]:
    run_dirs = _find_run_dirs()
    if not run_dirs:
        _ensure_minimum_seed_run()
        run_dirs = _find_run_dirs()
    _ensure_seed_suite_background()
    return run_dirs


def _find_run_dirs() -> list[Path]:
    if not OUTPUTS_DIR.exists():
        return []
    run_dirs = []
    seed_suite_ready = _seed_suite_ready()
    minimum_seed_dir = (WEB_RUNS_DIR / "nominal_ascent_seed").resolve()
    seed_suite_dir = _seed_suite_dir().resolve()
    for summary_path in OUTPUTS_DIR.rglob("summary.json"):
        run_dir = summary_path.parent
        resolved = run_dir.resolve()
        if (
            (resolved == minimum_seed_dir or _is_within(resolved, seed_suite_dir))
            and not _run_has_required_history_columns(run_dir)
        ):
            continue
        if seed_suite_ready and run_dir.resolve() == minimum_seed_dir:
            continue
        if (run_dir / "history.csv").exists():
            run_dirs.append(run_dir)
    return run_dirs


def _discover_missile_showcase_run_dirs(*, max_runs: int = 4) -> list[Path]:
    preferred_order = {
        "missile_head_on_showcase": 0,
        "missile_crossing_showcase": 1,
        "missile_tail_chase_showcase": 2,
        "missile_intercept_demo": 3,
    }
    latest_by_scenario: dict[str, Path] = {}
    for path in _discover_run_dirs():
        if not is_missile_showcase_run(path):
            continue
        summary = _read_json(path / "summary.json")
        scenario = str(summary.get("scenario", path.name))
        key = scenario.lower()
        previous = latest_by_scenario.get(key)
        if previous is None or path.stat().st_mtime > previous.stat().st_mtime:
            latest_by_scenario[key] = path
    run_dirs = sorted(
        latest_by_scenario.values(),
        key=lambda path: (
            preferred_order.get(str(_read_json(path / "summary.json").get("scenario", path.name)).lower(), 99),
            str(_read_json(path / "summary.json").get("scenario", path.name)).lower(),
        ),
    )
    return run_dirs[:max_runs]


def _ensure_minimum_seed_run() -> None:
    with SEED_LOCK:
        if _find_run_dirs():
            return
        scenario_path = SCENARIOS_DIR / "nominal_ascent.json"
        if not scenario_path.exists():
            return
        try:
            run_scenario(Scenario.from_file(scenario_path), WEB_RUNS_DIR / "nominal_ascent_seed")
        except (OSError, ValueError):
            return


def _ensure_seed_suite_background() -> None:
    global SEED_SUITE_STARTED
    if _seed_suite_ready() or not SCENARIOS_DIR.exists():
        return
    with SEED_LOCK:
        if SEED_SUITE_STARTED or _seed_suite_ready():
            return
        SEED_SUITE_STARTED = True
    EXECUTOR.submit(_seed_suite_worker, SCENARIOS_DIR, _seed_suite_dir())


def _seed_suite_worker(scenarios_dir: Path, seed_dir: Path) -> None:
    global SEED_SUITE_STARTED
    try:
        result = batch_run(scenarios_dir, seed_dir)
        write_json(seed_dir / ".seed_complete.json", {"generated_at_utc": _utc_now(), "scenario_count": result.get("count", 0)})
    except Exception:  # pragma: no cover - defensive reset for background worker failures
        with SEED_LOCK:
            SEED_SUITE_STARTED = False


def _seed_suite_dir() -> Path:
    return WEB_RUNS_DIR / "seed_scenario_suite"


def _seed_suite_marker() -> Path:
    return _seed_suite_dir() / ".seed_complete.json"


def _seed_suite_ready() -> bool:
    marker = _seed_suite_marker()
    if not marker.exists():
        return False
    scenario_count = len(list(SCENARIOS_DIR.glob("*.json")))
    run_count = sum(
        1
        for path in _seed_suite_dir().glob("*/summary.json")
        if (path.parent / "history.csv").exists() and _run_has_required_history_columns(path.parent)
    )
    return scenario_count > 0 and run_count >= scenario_count


def _run_has_required_history_columns(run_dir: Path) -> bool:
    history = run_dir / "history.csv"
    if not history.exists():
        return False
    try:
        with history.open("r", encoding="utf-8") as handle:
            header = handle.readline().strip().split(",")
    except OSError:
        return False
    return REQUIRED_HISTORY_COLUMNS.issubset(set(header))


def _build_run_summary(run_dir: Path) -> RunSummary:
    run_dir = run_dir.resolve()
    if not _is_within(run_dir, OUTPUTS_DIR.resolve()) or not (run_dir / "summary.json").exists():
        raise HTTPException(status_code=404, detail="run not found")
    summary = _read_json(run_dir / "summary.json")
    manifest = _read_json(run_dir / "manifest.json") if (run_dir / "manifest.json").exists() else None
    events = _read_json(run_dir / "events.json") if (run_dir / "events.json").exists() else []
    if not isinstance(events, list):
        events = []
    run_id = _run_id(run_dir)
    created = None
    if manifest:
        created = manifest.get("generated_at_utc")
    return RunSummary(
        id=run_id,
        scenario=str(summary.get("scenario", run_dir.name)),
        status="completed",
        run_dir=_repo_relative(run_dir),
        created_at_utc=created,
        summary=_safe_json(summary),
        manifest=_safe_json(manifest) if manifest else None,
        events=_safe_json(events),
        artifacts=_list_artifacts(run_id, run_dir),
    )


def _list_artifacts(run_id: str, run_dir: Path) -> list[ArtifactRef]:
    refs: list[ArtifactRef] = []
    candidates: list[Path] = []
    for name in (
        "report.html",
        "history.csv",
        "truth.csv",
        "controls.csv",
        "sensors.csv",
        "targets.csv",
        "interceptors.csv",
        "summary.json",
        "manifest.json",
        "events.json",
        "scenario_resolved.json",
    ):
        path = run_dir / name
        if path.exists():
            candidates.append(path)
    candidates.extend(sorted((run_dir / "plots").glob("*.svg"))[:100])
    sensor_dir = run_dir / "sensor_report"
    if sensor_dir.exists():
        candidates.extend(sorted(path for path in sensor_dir.glob("*") if path.is_file()))
    for path in sorted(run_dir.rglob("*")):
        if len(candidates) >= 180:
            break
        if not path.is_file() or path in candidates:
            continue
        if path.suffix.lower() in {".html", ".svg", ".csv", ".json"}:
            candidates.append(path)
    seen: set[str] = set()
    for path in candidates:
        rel = path.relative_to(run_dir).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        refs.append(
            ArtifactRef(
                name=path.name,
                kind=_artifact_kind(path),
                path=rel,
                url=f"/api/artifacts/{run_id}/{rel}",
                size_bytes=path.stat().st_size,
            )
        )
    return refs


def _artifact_kind(path: Path) -> str:
    if path.suffix == ".html":
        return "report"
    if path.suffix == ".svg":
        return "plot"
    if path.suffix == ".csv":
        return "csv"
    if path.suffix == ".json":
        return "json"
    return "file"


def _run_id(run_dir: Path) -> str:
    return run_dir.resolve().relative_to(OUTPUTS_DIR.resolve()).as_posix().replace("/", "~")


def _run_dir_from_id(run_id: str) -> Path:
    rel = run_id.replace("~", "/")
    candidate = (OUTPUTS_DIR / rel).resolve()
    if not _is_within(candidate, OUTPUTS_DIR.resolve()) or not (candidate / "summary.json").exists():
        raise HTTPException(status_code=404, detail="run not found")
    return candidate


def _output_dir_from_id(output_id: str) -> Path:
    rel = output_id.replace("~", "/")
    candidate = (OUTPUTS_DIR / rel).resolve()
    if not _is_within(candidate, OUTPUTS_DIR.resolve()) or not candidate.is_dir():
        raise HTTPException(status_code=404, detail="output not found")
    return candidate


def _action_dir(action: str, label: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return WEB_RUNS_DIR / f"{_run_slug(action)}_{_run_slug(label)}_{timestamp}"


def _action_result(action: str, output_dir: Path, data: dict[str, Any]) -> ActionResult:
    output_dir = output_dir.resolve()
    output_id = _run_id(output_dir) if _is_within(output_dir, OUTPUTS_DIR.resolve()) else None
    artifacts = _list_artifacts(output_id, output_dir) if output_id and output_dir.exists() else []
    return ActionResult(
        action=action,
        output_id=output_id,
        output_dir=_repo_relative(output_dir),
        data=_safe_json(data),
        artifacts=artifacts,
    )


def _run_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip().lower()).strip("._-")
    return slug or "run"


def _parse_value_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    values: list[Any] = []
    for item in str(value).split(","):
        text = item.strip()
        if not text:
            continue
        try:
            values.append(float(text))
        except ValueError:
            values.append(text)
    if not values:
        raise ValueError("value list must contain at least one value")
    return values


def _float_list(value: Any) -> list[float]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [float(item) for item in value]
    return [float(part.strip()) for part in str(value).split(",") if part.strip()]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _is_within(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _safe_json(value) for key, value in row.items()}


def _safe_json(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_json(item) for item in value]
    return value


app = create_app()
