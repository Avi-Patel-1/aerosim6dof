"""Scenario runner and artifact generation."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from aerosim6dof.analysis.metrics import summarize
from aerosim6dof.analysis.engagement import engagement_report
from aerosim6dof.config import load_json
from aerosim6dof.core.integration import adaptive_rk45_step, rk2_step, rk4_step
from aerosim6dof.core.quaternions import from_euler, normalize
from aerosim6dof.core.vectors import vec3
from aerosim6dof.environment.terrain import TerrainModel
from aerosim6dof.environment.wind import WindModel
from aerosim6dof.gnc.autopilot import Autopilot
from aerosim6dof.gnc.guidance import GuidanceModel
from aerosim6dof.gnc.navigation_hooks import NavigationHook
from aerosim6dof.metadata import VERSION
from aerosim6dof.reports.csv_writer import read_csv, write_csv
from aerosim6dof.reports.html import write_batch_report, write_report
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.svg import write_time_plot, write_xy_plot
from aerosim6dof.scenario import Scenario
from aerosim6dof.sensors.sensor_suite import SensorSuite
from aerosim6dof.vehicle.actuators import ActuatorSet
from aerosim6dof.vehicle.aerodynamics import AerodynamicModel
from aerosim6dof.vehicle.geometry import ReferenceGeometry
from aerosim6dof.vehicle.mass_properties import MassProperties
from aerosim6dof.vehicle.propulsion import PropulsionModel
from aerosim6dof.vehicle.state import VehicleState

from .contact import GroundContactModel, ground_contact_config
from .dynamics import DynamicsModel
from .events import EventDetector
from .interceptors import InterceptorSuite
from .logger import build_rows
from .monte_carlo_hooks import perturb_scenario
from .targets import TargetSuite


def run_scenario(scenario: Scenario, out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    components = _build_components(scenario)
    state = _initial_state(scenario, components["mass_properties"])
    wind_model: WindModel = components["wind"]
    terrain: TerrainModel = components["terrain"]
    contact_model: GroundContactModel = components["contact"]
    targets: TargetSuite = components["targets"]
    interceptors: InterceptorSuite = components["interceptors"]
    dynamics: DynamicsModel = components["dynamics"]
    guidance_model: GuidanceModel = components["guidance"]
    autopilot: Autopilot = components["autopilot"]
    navigation: NavigationHook = components["navigation"]
    actuators: ActuatorSet = components["actuators"]
    sensors: SensorSuite = components["sensors"]
    detector = EventDetector(scenario.events)
    history_rows: list[dict[str, Any]] = []
    truth_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    sensor_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    interceptor_rows: list[dict[str, Any]] = []
    controls_eff: dict[str, float] = {"elevator": 0.0, "aileron": 0.0, "rudder": 0.0, "throttle": 0.0}
    steps = int(math.floor(scenario.duration / scenario.dt)) + 1
    for step in range(steps):
        t = step * scenario.dt
        terrain_state = terrain.query(state.position_m, state.velocity_mps)
        contact_state = contact_model.evaluate(terrain_state)
        wind_sample = wind_model.sample(t, state.position_m, float(np.linalg.norm(state.velocity_mps)), scenario.dt)
        pre_eval = dynamics.evaluate(t, state, controls_eff, wind_sample.velocity_mps)
        nav = navigation.estimate(state, sensors.last_values)
        guidance = guidance_model.command(t, state, nav)
        surface_commands = autopilot.command(state, guidance, pre_eval.aero.qbar_pa, scenario.dt, pre_eval.aero.beta_rad)
        controls_eff, actuator_flags = actuators.step(surface_commands, scenario.dt, t)
        controls_eff["throttle"] = surface_commands.get("throttle", guidance.throttle)
        evaluation = dynamics.evaluate(t, state, controls_eff, wind_sample.velocity_mps, dt=scenario.dt)
        sensor_values = sensors.sample(
            t,
            scenario.dt,
            {
                "position_m": state.position_m,
                "velocity_mps": state.velocity_mps,
                "quaternion": state.quaternion,
                "rates_rps": state.rates_rps,
                "accel_body_mps2": evaluation.acceleration_body_mps2,
                "airspeed_mps": evaluation.airspeed_mps,
                "qbar_pa": evaluation.aero.qbar_pa,
                "mach": evaluation.aero.mach,
                "terrain_elevation_m": terrain_state["terrain_elevation_m"],
                "altitude_agl_m": terrain_state["altitude_agl_m"],
            },
        )
        target_state, target_samples = targets.sample(t, state.position_m, state.velocity_mps)
        interceptor_state, interceptor_samples, interceptor_events = interceptors.step(t, scenario.dt, state.position_m, state.velocity_mps, target_samples)
        target_rows.extend(target_samples)
        interceptor_rows.extend(interceptor_samples)
        for event in interceptor_events:
            detector.add(event)
        history, truth, controls, sensor_row = build_rows(
            t,
            state,
            evaluation,
            guidance,
            surface_commands,
            controls_eff,
            actuator_flags,
            sensor_values,
            terrain_elevation_m=terrain_state["terrain_elevation_m"],
            altitude_agl_m=terrain_state["altitude_agl_m"],
            contact_state=contact_state,
            target_state=target_state,
            interceptor_state=interceptor_state,
        )
        history_rows.append(history)
        truth_rows.append(truth)
        control_rows.append(controls)
        sensor_rows.append(sensor_row)
        stop = detector.update(history, controls, terrain_state["altitude_agl_m"], contact_state)
        if stop or step == steps - 1:
            break
        state = _advance_state(scenario.integrator, dynamics, state, controls_eff, wind_sample.velocity_mps, t, scenario.dt)
        state, _contact_action = contact_model.apply(state, terrain)
        if terrain.above_ground(state.position_m) < -50.0:
            break
    for event in interceptors.finalize_events():
        detector.add(event)
    events = detector.finalize()
    summary = summarize(history_rows, events, scenario.name)
    _write_artifacts(out, scenario, summary, events, history_rows, truth_rows, control_rows, sensor_rows, target_rows, interceptor_rows)
    return summary


def batch_run(scenario_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    scenario_paths = sorted(Path(scenario_dir).glob("*.json"))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summaries = []
    for path in scenario_paths:
        run_out = out / path.stem
        summary = run_scenario(Scenario.from_file(path), run_out)
        summary["run_dir"] = str(run_out)
        summaries.append(summary)
    batch_summary = {"runs": summaries, "count": len(summaries)}
    write_json(out / "batch_summary.json", batch_summary)
    write_csv(out / "batch_index.csv", _summary_index_rows(summaries))
    write_batch_report(out, batch_summary)
    return batch_summary


def report_run(run_dir: str | Path) -> Path:
    run = Path(run_dir)
    if not (run / "history.csv").exists() and (run / "batch_summary.json").exists():
        summary = json.loads((run / "batch_summary.json").read_text())
        filename = "monte_carlo_report.html" if summary.get("kind") == "monte_carlo" else "batch_report.html"
        return write_batch_report(run, summary, filename=filename)
    history = read_csv(run / "history.csv")
    summary = json.loads((run / "summary.json").read_text()) if (run / "summary.json").exists() else summarize(history, [], run.name)
    events = json.loads((run / "events.json").read_text()) if (run / "events.json").exists() else []
    plots = _generate_plots(run, history)
    return write_report(run, summary, events, plots)


def monte_carlo_run(
    scenario: Scenario,
    samples: int,
    out_dir: str | Path,
    seed: int = 1,
    dispersions: dict[str, float] | None = None,
) -> dict[str, Any]:
    if samples <= 0:
        raise ValueError("samples must be a positive integer")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    for idx in range(samples):
        sample_seed = int(seed) + idx
        data = perturb_scenario(json.loads(json.dumps(scenario.raw)), sample_seed, dispersions or {})
        sample_name = f"{scenario.name}_mc_{idx:03d}"
        data["name"] = sample_name
        run_out = out / sample_name
        sample_summary = run_scenario(Scenario.from_dict(data, source_path=scenario.source_path), run_out)
        sample_summary["sample_index"] = idx
        sample_summary["seed"] = sample_seed
        sample_summary["run_dir"] = str(run_out)
        sample_summary["dispersions"] = dispersions or {}
        summaries.append(sample_summary)
    aggregate = _monte_carlo_aggregate(scenario.name, summaries, dispersions or {})
    write_json(out / "monte_carlo_summary.json", aggregate)
    write_json(out / "batch_summary.json", {"runs": summaries, "count": len(summaries), "kind": "monte_carlo"})
    write_csv(out / "monte_carlo_index.csv", _summary_index_rows(summaries))
    stale_batch_report = out / "batch_report.html"
    if stale_batch_report.exists():
        stale_batch_report.unlink()
    write_batch_report(out, {"runs": summaries, "count": len(summaries)}, filename="monte_carlo_report.html")
    return aggregate


def linearize_scenario(scenario: Scenario, time_s: float, out_dir: str | Path) -> dict[str, Any]:
    components = _build_components(scenario)
    state = _initial_state(scenario, components["mass_properties"])
    dynamics: DynamicsModel = components["dynamics"]
    wind = np.zeros(3, dtype=float)
    controls = {"elevator": 0.0, "aileron": 0.0, "rudder": 0.0, "throttle": float(scenario.guidance.get("throttle", 0.8))}
    for step in range(max(0, int(time_s / scenario.dt))):
        state = _advance_state("rk4", dynamics, state, controls, wind, step * scenario.dt, scenario.dt)
    x0 = state.pack()
    u0 = np.array([controls["elevator"], controls["aileron"], controls["rudder"], controls["throttle"]], dtype=float)
    def f_state(x: np.ndarray) -> np.ndarray:
        return dynamics.evaluate(time_s, VehicleState.unpack(x), controls, wind).derivative
    def f_control(u: np.ndarray) -> np.ndarray:
        c = {"elevator": u[0], "aileron": u[1], "rudder": u[2], "throttle": u[3]}
        return dynamics.evaluate(time_s, state, c, wind).derivative
    from aerosim6dof.gnc.trim import numerical_jacobian

    a_mat = numerical_jacobian(f_state, x0, eps=1e-4)
    b_mat = numerical_jacobian(f_control, u0, eps=1e-4)
    result = {
        "state_order": [
            "x",
            "y",
            "z",
            "vx",
            "vy",
            "vz",
            "qw",
            "qx",
            "qy",
            "qz",
            "p",
            "q",
            "r",
            "mass",
        ],
        "control_order": ["elevator", "aileron", "rudder", "throttle"],
        "A": a_mat.tolist(),
        "B": b_mat.tolist(),
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "linearization.json", result)
    write_csv(out / "A_matrix.csv", _matrix_rows(a_mat))
    write_csv(out / "B_matrix.csv", _matrix_rows(b_mat))
    return result


def _build_components(scenario: Scenario) -> dict[str, Any]:
    vehicle = scenario.vehicle
    geometry = ReferenceGeometry.from_config(vehicle.get("reference", {}))
    mass = MassProperties(vehicle)
    propulsion = PropulsionModel(vehicle.get("propulsion", {}))
    aero = AerodynamicModel(vehicle.get("aero", {}))
    return {
        "geometry": geometry,
        "mass_properties": mass,
        "propulsion": propulsion,
        "aero": aero,
        "dynamics": DynamicsModel(aero, propulsion, mass, geometry),
        "wind": WindModel(scenario.wind, seed=int(scenario.sensors.get("seed", 7)) + 101),
        "terrain": TerrainModel(scenario.environment.get("terrain", {})),
        "contact": GroundContactModel(ground_contact_config(scenario)),
        "targets": TargetSuite.from_scenario(scenario),
        "interceptors": InterceptorSuite.from_scenario(scenario),
        "guidance": GuidanceModel(scenario.guidance),
        "autopilot": Autopilot({**scenario.guidance.get("autopilot", {}), **scenario.autopilot}),
        "navigation": NavigationHook(str(scenario.guidance.get("navigation", scenario.sensors.get("navigation", "truth")))),
        "actuators": ActuatorSet(vehicle.get("actuators", {})),
        "sensors": SensorSuite(scenario.sensors),
    }


def _initial_state(scenario: Scenario, mass: MassProperties) -> VehicleState:
    initial = scenario.initial
    euler = np.deg2rad(vec3(initial.get("euler_deg"), (0.0, 5.0, 0.0)))
    return VehicleState(
        position_m=vec3(initial.get("position_m"), (0.0, 0.0, 0.0)),
        velocity_mps=vec3(initial.get("velocity_mps"), (80.0, 0.0, 5.0)),
        quaternion=from_euler(float(euler[0]), float(euler[1]), float(euler[2])),
        rates_rps=np.deg2rad(vec3(initial.get("body_rates_dps"), (0.0, 0.0, 0.0))),
        mass_kg=float(initial.get("mass_kg", mass.initial_mass_kg)),
    )


def _advance_state(
    integrator: str,
    dynamics: DynamicsModel,
    state: VehicleState,
    controls: dict[str, float],
    wind_mps: np.ndarray,
    t: float,
    dt: float,
) -> VehicleState:
    if integrator in {"rk2", "rk4", "adaptive_rk45"}:
        def fn(t_sub: float, y: np.ndarray) -> np.ndarray:
            sub_state = VehicleState.unpack(y)
            return dynamics.evaluate(t_sub, sub_state, controls, wind_mps).derivative
        if integrator == "rk2":
            y_next = rk2_step(fn, t, state.pack(), dt)
        elif integrator == "adaptive_rk45":
            y_next, _, _ = adaptive_rk45_step(fn, t, state.pack(), dt)
        else:
            y_next = rk4_step(fn, t, state.pack(), dt)
        nxt = VehicleState.unpack(y_next)
    else:
        ev = dynamics.evaluate(t, state, controls, wind_mps)
        nxt = state.copy()
        if integrator == "semi_implicit_euler":
            nxt.velocity_mps = nxt.velocity_mps + ev.acceleration_inertial_mps2 * dt
            nxt.position_m = nxt.position_m + nxt.velocity_mps * dt
        else:
            nxt.position_m = nxt.position_m + nxt.velocity_mps * dt
            nxt.velocity_mps = nxt.velocity_mps + ev.acceleration_inertial_mps2 * dt
        nxt.rates_rps = np.clip(nxt.rates_rps + ev.angular_accel_rps2 * dt, -np.deg2rad(520.0), np.deg2rad(520.0))
        from aerosim6dof.core.quaternions import integrate

        nxt.quaternion = integrate(nxt.quaternion, nxt.rates_rps, dt)
        nxt.mass_kg = nxt.mass_kg + ev.derivative[-1] * dt
    nxt.quaternion = normalize(nxt.quaternion)
    nxt.mass_kg = max(dynamics.mass_properties.dry_mass_kg, float(nxt.mass_kg))
    return nxt


def _write_artifacts(
    out: Path,
    scenario: Scenario,
    summary: dict[str, Any],
    events: list[dict[str, Any]],
    history: list[dict[str, Any]],
    truth: list[dict[str, Any]],
    controls: list[dict[str, Any]],
    sensors: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    interceptors: list[dict[str, Any]],
) -> None:
    write_csv(out / "history.csv", history)
    write_csv(out / "truth.csv", truth)
    write_csv(out / "controls.csv", controls)
    write_csv(out / "sensors.csv", sensors)
    target_files: list[str] = []
    if targets:
        write_csv(out / "targets.csv", targets)
        target_files.append("targets.csv")
    if interceptors:
        write_csv(out / "interceptors.csv", interceptors)
        target_files.append("interceptors.csv")
    write_json(out / "events.json", events)
    write_json(out / "summary.json", summary)
    write_json(out / "scenario_resolved.json", scenario.raw)
    plots = _generate_plots(out, history)
    write_report(out, summary, events, plots)
    engagement_files: list[str] = []
    if targets or interceptors:
        engagement_report(out)
        engagement_files.extend(["engagement_report.html", "engagement_report.json"])
    write_json(
        out / "manifest.json",
        {
            "aerosim6dof_version": VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "scenario": scenario.name,
            "integrator": scenario.integrator,
            "dt": scenario.dt,
            "duration": scenario.duration,
            "sample_count": len(history),
            "files": [
                "history.csv",
                "truth.csv",
                "controls.csv",
                "sensors.csv",
                *target_files,
                "events.json",
                "summary.json",
                "scenario_resolved.json",
                "report.html",
                *engagement_files,
                *[str(p.relative_to(out)) for p in plots],
            ],
        },
    )


def _generate_plots(out: Path, rows: list[dict[str, Any]]) -> list[Path]:
    plots_dir = out / "plots"
    specs = [
        ("01_altitude_m.svg", "time", ["altitude_m"], "Altitude", "altitude (m)"),
        ("02_downrange_crossrange.svg", "xy", ["y_m"], "Downrange/Crossrange", "crossrange (m)"),
        ("03_position_x.svg", "time", ["x_m"], "Downrange Position", "x (m)"),
        ("04_position_y.svg", "time", ["y_m"], "Crossrange Position", "y (m)"),
        ("05_position_z.svg", "time", ["altitude_m"], "Altitude Position", "z (m)"),
        ("06_velocity_x.svg", "time", ["vx_mps"], "Velocity X", "vx (m/s)"),
        ("07_velocity_y.svg", "time", ["vy_mps"], "Velocity Y", "vy (m/s)"),
        ("08_velocity_z.svg", "time", ["vz_mps"], "Velocity Z", "vz (m/s)"),
        ("09_speed_mps.svg", "time", ["speed_mps", "airspeed_mps"], "Speed", "speed (m/s)"),
        ("10_euler_deg.svg", "time", ["roll_deg", "pitch_deg", "yaw_deg"], "Euler Angles", "angle (deg)"),
        ("11_body_rates_dps.svg", "time", ["p_dps", "q_dps", "r_dps"], "Body Rates", "rate (deg/s)"),
        ("12_alpha_beta_deg.svg", "time", ["alpha_deg", "beta_deg"], "Alpha/Beta", "angle (deg)"),
        ("13_mach.svg", "time", ["mach"], "Mach Number", "Mach"),
        ("14_qbar_pa.svg", "time", ["qbar_pa"], "Dynamic Pressure", "qbar (Pa)"),
        ("15_load_factor_g.svg", "time", ["load_factor_g"], "Load Factor", "g"),
        ("16_mass_kg.svg", "time", ["mass_kg"], "Mass", "mass (kg)"),
        ("17_thrust_n.svg", "time", ["thrust_n"], "Thrust", "thrust (N)"),
        ("18_surfaces_deg.svg", "time", ["elevator_deg", "aileron_deg", "rudder_deg"], "Control Surfaces", "deflection (deg)"),
        ("19_actuator_saturation.svg", "time", ["elevator_saturated", "aileron_saturated", "rudder_saturated"], "Actuator Saturation", "flag"),
        ("20_wind_components.svg", "time", ["wind_x_mps", "wind_y_mps", "wind_z_mps"], "Wind Components", "wind (m/s)"),
        ("21_gps_altitude_truth.svg", "time", ["altitude_m", "gps_z_m"], "GPS Altitude vs Truth", "altitude (m)"),
        ("22_barometer_truth.svg", "time", ["altitude_m", "baro_alt_m"], "Barometer vs Truth", "altitude (m)"),
        ("23_pitch_command_tracking.svg", "time", ["pitch_command_deg", "pitch_deg"], "Pitch Command Tracking", "pitch (deg)"),
        ("24_heading_command_tracking.svg", "time", ["heading_command_deg", "yaw_deg"], "Heading Command Tracking", "heading (deg)"),
        ("25_energy_proxy.svg", "time", ["energy_j_per_kg"], "Specific Energy", "J/kg"),
        ("26_qbar_load_envelope.svg", "xy_qbar", ["load_factor_g"], "Qbar/Load Envelope", "load factor (g)"),
        ("27_target_distance.svg", "time", ["target_distance_m"], "Target Distance", "distance (m)"),
        ("28_agl_terrain.svg", "time", ["altitude_m", "terrain_elevation_m", "altitude_agl_m"], "Terrain/AGL", "altitude (m)"),
        ("29_ground_contact.svg", "time", ["ground_contact", "impact_speed_mps", "altitude_agl_rate_mps"], "Ground Contact", "contact"),
        ("30_target_kinematics.svg", "time", ["target_range_m", "closing_speed_mps", "target_range_rate_mps"], "Target Kinematics", "target"),
        ("31_interceptor_kinematics.svg", "time", ["interceptor_range_m", "interceptor_closing_speed_mps", "interceptor_time_to_go_s"], "Interceptor Kinematics", "interceptor"),
    ]
    paths: list[Path] = []
    for filename, mode, keys, title, label in specs:
        path = plots_dir / filename
        if mode == "time":
            write_time_plot(path, rows, keys, title, label)
        elif mode == "xy_qbar":
            write_xy_plot(path, rows, "qbar_pa", keys, title, "qbar (Pa)", label)
        else:
            write_xy_plot(path, rows, "x_m", keys, title, "downrange (m)", label)
        paths.append(path)
    return paths


def _matrix_rows(mat: np.ndarray) -> list[dict[str, float]]:
    rows = []
    for i in range(mat.shape[0]):
        row = {"row": float(i)}
        for j in range(mat.shape[1]):
            row[f"c{j}"] = float(mat[i, j])
        rows.append(row)
    return rows


def load_vehicle_config(path: str | Path) -> dict[str, Any]:
    return load_json(path)


def _summary_index_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        final = summary.get("final", {}) if isinstance(summary.get("final"), dict) else {}
        rows.append(
            {
                "scenario": summary.get("scenario", ""),
                "sample_index": summary.get("sample_index", ""),
                "seed": summary.get("seed", ""),
                "duration_s": summary.get("duration_s", ""),
                "final_x_m": final.get("x_m", ""),
                "final_y_m": final.get("y_m", ""),
                "final_altitude_m": final.get("altitude_m", ""),
                "final_speed_mps": final.get("speed_mps", ""),
                "max_altitude_m": summary.get("max_altitude_m", ""),
                "max_speed_mps": summary.get("max_speed_mps", ""),
                "max_load_factor_g": summary.get("max_load_factor_g", ""),
                "max_qbar_pa": summary.get("max_qbar_pa", ""),
                "event_count": summary.get("event_count", ""),
                "run_dir": summary.get("run_dir", ""),
            }
        )
    return rows


def _monte_carlo_aggregate(
    base_scenario: str,
    summaries: list[dict[str, Any]],
    dispersions: dict[str, float],
) -> dict[str, Any]:
    final_altitudes = [float(s["final"]["altitude_m"]) for s in summaries]
    max_qbars = [float(s["max_qbar_pa"]) for s in summaries]
    max_loads = [float(s["max_load_factor_g"]) for s in summaries]
    return {
        "scenario": base_scenario,
        "samples": len(summaries),
        "dispersions": dispersions,
        "final_altitude_mean_m": float(np.mean(final_altitudes)),
        "final_altitude_std_m": float(np.std(final_altitudes)),
        "max_qbar_mean_pa": float(np.mean(max_qbars)),
        "max_qbar_std_pa": float(np.std(max_qbars)),
        "max_load_factor_mean_g": float(np.mean(max_loads)),
        "max_load_factor_std_g": float(np.std(max_loads)),
        "runs": summaries,
    }
