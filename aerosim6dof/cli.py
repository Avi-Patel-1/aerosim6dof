"""Command line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from aerosim6dof.analysis.aero import aero_report, aero_sweep, inspect_aero
from aerosim6dof.analysis.compare import compare_histories
from aerosim6dof.analysis.config_tools import config_diff, generate_scenario, inspect_vehicle
from aerosim6dof.analysis.environment import environment_report
from aerosim6dof.analysis.engagement import engagement_report
from aerosim6dof.analysis.propulsion import inspect_propulsion, thrust_curve_report
from aerosim6dof.analysis.sensors import sensor_report
from aerosim6dof.analysis.stability import linear_model_report, stability_report, trim_sweep
from aerosim6dof.analysis.validation import validate
from aerosim6dof.config import load_json
from aerosim6dof.gnc.trim import simple_trim, write_trim_result
from aerosim6dof.scenario import Scenario
from aerosim6dof.simulation.campaign import run_sweep_campaign
from aerosim6dof.simulation.fault_campaign import FAULT_LIBRARY, run_fault_campaign
from aerosim6dof.simulation.runner import batch_run, linearize_scenario, monte_carlo_run, report_run, run_scenario


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="aerosim6dof", description="Run and analyze 6-DOF flight vehicle simulations.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a JSON scenario.")
    run.add_argument("--scenario", required=True, help="Path to scenario JSON.")
    run.add_argument("--out", required=True, help="Output directory.")

    batch = sub.add_parser("batch", help="Run every scenario JSON in a directory.")
    batch.add_argument("--scenarios", required=True, help="Directory containing scenario JSON files.")
    batch.add_argument("--out", required=True, help="Output directory.")

    validate_cmd = sub.add_parser("validate", help="Validate a scenario JSON file.")
    validate_cmd.add_argument("--scenario", required=True, help="Path to scenario JSON.")

    compare = sub.add_parser("compare", help="Compare two history CSV outputs.")
    compare.add_argument("--a", required=True, help="First history CSV.")
    compare.add_argument("--b", required=True, help="Second history CSV.")
    compare.add_argument("--out", required=True, help="Output directory.")

    trim = sub.add_parser("trim", help="Compute a simple steady-flight trim estimate.")
    trim.add_argument("--vehicle", required=True, help="Vehicle config JSON.")
    trim.add_argument("--speed", required=True, type=float, help="Trim speed in m/s.")
    trim.add_argument("--altitude", required=True, type=float, help="Trim altitude in m.")
    trim.add_argument("--out", required=True, help="Output directory.")

    linearize = sub.add_parser("linearize", help="Numerically linearize a scenario at a time.")
    linearize.add_argument("--scenario", required=True, help="Path to scenario JSON.")
    linearize.add_argument("--time", required=True, type=float, help="Linearization time in seconds.")
    linearize.add_argument("--out", required=True, help="Output directory.")

    stability_cmd = sub.add_parser("stability", help="Analyze eigenvalues from a linearization file.")
    stability_cmd.add_argument("--linearization", required=True, help="Path to linearization.json.")
    stability_cmd.add_argument("--out", required=True, help="Output directory.")

    trim_sweep_cmd = sub.add_parser("trim-sweep", help="Run a trim grid over speeds and altitudes.")
    trim_sweep_cmd.add_argument("--vehicle", required=True)
    trim_sweep_cmd.add_argument("--speeds", required=True, help="Comma-separated speeds in m/s.")
    trim_sweep_cmd.add_argument("--altitudes", required=True, help="Comma-separated altitudes in m.")
    trim_sweep_cmd.add_argument("--out", required=True)

    linear_report_cmd = sub.add_parser("linear-model-report", help="Summarize a linearization and stability analysis.")
    linear_report_cmd.add_argument("--linearization", required=True)
    linear_report_cmd.add_argument("--out", required=True)

    report = sub.add_parser("report", help="Regenerate the HTML report and SVG suite for a run directory.")
    report.add_argument("--run", required=True, help="Run output directory.")

    monte = sub.add_parser("monte-carlo", help="Run a dispersed Monte Carlo set from one scenario.")
    monte.add_argument("--scenario", required=True, help="Path to scenario JSON.")
    monte.add_argument("--samples", required=True, type=int, help="Number of samples to run.")
    monte.add_argument("--out", required=True, help="Output directory.")
    monte.add_argument("--seed", type=int, default=1, help="Base random seed.")
    monte.add_argument("--mass-sigma-kg", type=float, default=0.0, help="One-sigma vehicle mass dispersion.")
    monte.add_argument("--wind-sigma-mps", type=float, default=0.0, help="One-sigma steady-wind dispersion per axis.")

    inspect_vehicle_cmd = sub.add_parser("inspect-vehicle", help="Inspect a vehicle configuration.")
    inspect_vehicle_cmd.add_argument("--vehicle", required=True)

    diff_cmd = sub.add_parser("config-diff", help="Diff two JSON configuration files.")
    diff_cmd.add_argument("--a", required=True)
    diff_cmd.add_argument("--b", required=True)

    gen = sub.add_parser("generate-scenario", help="Generate a runnable scenario template.")
    gen.add_argument("--out", required=True)
    gen.add_argument("--name", required=True)
    gen.add_argument("--vehicle-config", default="../vehicles/baseline.json")
    gen.add_argument("--environment-config", default="../environments/calm.json")
    gen.add_argument("--guidance-mode", default="pitch_program")

    inspect_aero_cmd = sub.add_parser("inspect-aero", help="Inspect aero model/database configuration.")
    inspect_aero_cmd.add_argument("--vehicle", required=True)

    aero_sweep_cmd = sub.add_parser("aero-sweep", help="Run an alpha/Mach aero coefficient sweep.")
    aero_sweep_cmd.add_argument("--vehicle", required=True)
    aero_sweep_cmd.add_argument("--out", required=True)
    aero_sweep_cmd.add_argument("--mach", default="", help="Comma-separated Mach values.")
    aero_sweep_cmd.add_argument("--alpha", default="", help="Comma-separated alpha values in degrees.")

    aero_report_cmd = sub.add_parser("aero-report", help="Build an aerodynamic HTML report.")
    aero_report_cmd.add_argument("--vehicle", required=True)
    aero_report_cmd.add_argument("--out", required=True)

    inspect_prop_cmd = sub.add_parser("inspect-propulsion", help="Inspect propulsion configuration.")
    inspect_prop_cmd.add_argument("--vehicle", required=True)

    thrust_report_cmd = sub.add_parser("thrust-curve-report", help="Build a thrust curve report.")
    thrust_report_cmd.add_argument("--vehicle", required=True)
    thrust_report_cmd.add_argument("--out", required=True)

    env_report_cmd = sub.add_parser("environment-report", help="Build an environment profile report.")
    env_report_cmd.add_argument("--environment", required=True)
    env_report_cmd.add_argument("--out", required=True)

    sensor_report_cmd = sub.add_parser("sensor-report", help="Build sensor error metrics and plots from a run directory.")
    sensor_report_cmd.add_argument("--run", required=True)
    sensor_report_cmd.add_argument("--out", default="")

    engagement_report_cmd = sub.add_parser("engagement-report", help="Build target/interceptor engagement metrics and plots from a run directory.")
    engagement_report_cmd.add_argument("--run", required=True)
    engagement_report_cmd.add_argument("--out", default="")

    sweep_cmd = sub.add_parser("sweep", help="Run a Cartesian parameter sweep campaign.")
    sweep_cmd.add_argument("--scenario", required=True)
    sweep_cmd.add_argument("--out", required=True)
    sweep_cmd.add_argument("--set", action="append", default=[], help="Dotted path with comma values, e.g. guidance.throttle=0.75,0.85")
    sweep_cmd.add_argument("--max-runs", type=int, default=200)

    fault_cmd = sub.add_parser("fault-campaign", help="Run built-in fault cases for one scenario.")
    fault_cmd.add_argument("--scenario", required=True)
    fault_cmd.add_argument("--out", required=True)
    fault_cmd.add_argument("--fault", action="append", default=[], help=f"Fault name. Available: {', '.join(sorted(FAULT_LIBRARY))}")
    fault_cmd.add_argument("--max-runs", type=int, default=50)

    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            result = run_scenario(Scenario.from_file(args.scenario), args.out)
        elif args.command == "batch":
            result = batch_run(args.scenarios, args.out)
        elif args.command == "validate":
            result = validate(args.scenario)
        elif args.command == "compare":
            result = compare_histories(args.a, args.b, args.out)
        elif args.command == "trim":
            result = simple_trim(load_json(args.vehicle), args.speed, args.altitude)
            write_trim_result(result, args.out)
        elif args.command == "linearize":
            result = linearize_scenario(Scenario.from_file(args.scenario), args.time, args.out)
        elif args.command == "stability":
            result = stability_report(args.linearization, args.out)
        elif args.command == "trim-sweep":
            speeds = _float_list(args.speeds) or []
            altitudes = _float_list(args.altitudes) or []
            if not speeds or not altitudes:
                raise ValueError("--speeds and --altitudes must contain at least one value")
            result = trim_sweep(args.vehicle, args.out, speeds, altitudes)
        elif args.command == "linear-model-report":
            result = linear_model_report(args.linearization, args.out)
        elif args.command == "report":
            path = report_run(args.run)
            result = {"report": str(Path(path))}
        elif args.command == "monte-carlo":
            dispersions = {}
            if args.mass_sigma_kg > 0.0:
                dispersions["mass_sigma_kg"] = args.mass_sigma_kg
            if args.wind_sigma_mps > 0.0:
                dispersions["wind_sigma_mps"] = args.wind_sigma_mps
            result = monte_carlo_run(Scenario.from_file(args.scenario), args.samples, args.out, args.seed, dispersions)
        elif args.command == "inspect-vehicle":
            result = inspect_vehicle(args.vehicle)
        elif args.command == "config-diff":
            result = config_diff(args.a, args.b)
        elif args.command == "generate-scenario":
            result = generate_scenario(args.out, args.name, args.vehicle_config, args.environment_config, args.guidance_mode)
        elif args.command == "inspect-aero":
            result = inspect_aero(args.vehicle)
        elif args.command == "aero-sweep":
            result = aero_sweep(args.vehicle, args.out, _float_list(args.mach), _float_list(args.alpha))
        elif args.command == "aero-report":
            result = aero_report(args.vehicle, args.out)
        elif args.command == "inspect-propulsion":
            result = inspect_propulsion(args.vehicle)
        elif args.command == "thrust-curve-report":
            result = thrust_curve_report(args.vehicle, args.out)
        elif args.command == "environment-report":
            result = environment_report(args.environment, args.out)
        elif args.command == "sensor-report":
            result = sensor_report(args.run, args.out or None)
        elif args.command == "engagement-report":
            result = engagement_report(args.run, args.out or None)
        elif args.command == "sweep":
            result = run_sweep_campaign(Scenario.from_file(args.scenario), args.out, _parse_sweep(args.set), args.max_runs)
        elif args.command == "fault-campaign":
            result = run_fault_campaign(Scenario.from_file(args.scenario), args.out, args.fault or None, args.max_runs)
        else:
            parser.error(f"unsupported command {args.command}")
            return
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(result, indent=2))


def _float_list(value: str) -> list[float] | None:
    if not value.strip():
        return None
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def _parse_sweep(items: list[str]) -> dict[str, list[object]]:
    sweep: dict[str, list[object]] = {}
    for item in items:
        if "=" not in item:
            raise ValueError("--set entries must use dotted.path=value1,value2")
        key, raw_values = item.split("=", 1)
        values: list[object] = []
        for raw in raw_values.split(","):
            text = raw.strip()
            if not text:
                continue
            try:
                values.append(float(text))
            except ValueError:
                values.append(text)
        if not values:
            raise ValueError(f"--set {key} has no values")
        sweep[key.strip()] = values
    return sweep


if __name__ == "__main__":
    main()
