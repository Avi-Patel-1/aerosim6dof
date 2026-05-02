# Production-Ready Feature Pass

This document captures the current production-ready surface for AeroSim 6DOF and the local checks expected before handing off a build. It covers the command-line simulator, browser workbench, durable outputs, scenario guardrails, reporting, replay, persistence, and engineering analysis tools.

## Productionized Surface

- Scenario execution: run, validate, compare, batch, Monte Carlo, parameter sweep, and fault-campaign workflows are available through the Python CLI and exposed in the browser workbench.
- Engineering analysis: trim, trim-sweep, linearization, stability, and linear-model reports produce reviewable JSON, CSV, SVG, and HTML artifacts.
- Vehicle and environment inspection: aerodynamic, propulsion, atmosphere, wind, terrain, and vehicle configuration reports are documented and scriptable.
- Sensor and navigation workflows: sensor logs, sensor error reports, dropout/fault visibility, and navigation telemetry are available from run artifacts.
- Scenario authoring: guided scenario-builder flows and raw JSON editing share the same validation path used by CLI execution.
- Web operations: launch, engineering, campaign, editor, replay, report, storage, and live-progress views are documented for local use.
- Persistent storage: local JSON-backed drafts and saved workbench objects use validated identifiers and namespaced storage.
- Replay and visualization: replay overlays, trail modes, legends, and run-detail artifacts support post-run inspection.
- Missile runtime: interceptor scenarios can opt into the missile dynamics path while legacy interceptor behavior remains available.
- Output contracts: run directories consistently expose machine-readable artifacts such as `summary.json`, `history.csv`, `truth.csv`, `controls.csv`, `sensors.csv`, `events.json`, and generated reports.

## Local Validation

Run the core Python checks:

```bash
python3 -m unittest discover -s tests
```

Validate representative scenarios:

```bash
python3 -m aerosim6dof validate --scenario examples/scenarios/nominal_ascent.json
python3 -m aerosim6dof validate --scenario examples/scenarios/gps_dropout_navigation.json
python3 -m aerosim6dof validate --scenario examples/scenarios/target_intercept.json
```

Exercise representative CLI outputs:

```bash
python3 -m aerosim6dof run --scenario examples/scenarios/nominal_ascent.json --out outputs/nominal_ascent_check
python3 -m aerosim6dof sensor-report --run outputs/nominal_ascent_check
python3 -m aerosim6dof fault-campaign --scenario examples/scenarios/nominal_ascent.json --out outputs/fault_campaign_check
python3 -m aerosim6dof trim-sweep --vehicle examples/vehicles/baseline.json --speeds 90,120,150 --altitudes 0,1000 --out outputs/trim_sweep_check
```

Check the browser workbench when frontend dependencies are installed:

```bash
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:5173` and verify that scenario validation, a nominal run, replay loading, campaign controls, engineering actions, and saved drafts are usable from the workbench.

## Release Checklist

- All Python tests pass.
- Representative scenarios validate without unexpected errors.
- A nominal run writes the expected CSV, JSON, and report artifacts.
- Sensor-report, fault-campaign, and trim-sweep commands complete and write HTML summaries.
- Web scenario validation matches CLI validation for the same draft.
- Saved drafts survive a browser refresh and remain editable.
- Live progress reaches a terminal state for completed, failed, and cancelled runs.
- Replay overlays render without hiding primary telemetry or controls.
- Documentation links reference existing files and commands.
- No user-facing documentation includes internal development wording.
