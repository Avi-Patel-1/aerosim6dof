# AeroSim 6DOF

`aerosim6dof` is a compact, inspectable six-degree-of-freedom flight simulation package for early GNC, vehicle concept, mission-performance, and sensor-analysis studies. It models rigid-body translation and rotation, quaternion attitude propagation, atmosphere and gravity variation, winds and gusts, propulsion and mass depletion, aerodynamic force and moment buildup, actuator dynamics, guidance/autopilot loops, sensor measurements, event detection, and report outputs.

The simulation core uses Python and NumPy. The browser dashboard is an optional FastAPI, React, Vite, TypeScript, and Three.js layer that wraps the same engine without replacing the command-line tools.

## Quick Start

```bash
python3 -m unittest discover -s tests
python3 -m aerosim6dof validate --scenario examples/scenarios/nominal_ascent.json
python3 -m aerosim6dof run --scenario examples/scenarios/nominal_ascent.json --out outputs/nominal_expanded
```

Run every packaged scenario:

```bash
python3 -m aerosim6dof batch --scenarios examples/scenarios --out outputs/batch_expanded
```

Run a dispersed Monte Carlo set:

```bash
python3 -m aerosim6dof monte-carlo --scenario examples/scenarios/nominal_ascent.json --samples 25 --seed 77 --mass-sigma-kg 0.2 --out outputs/monte_carlo_nominal
```

Generate a comparison, trim point, linear model, or report:

```bash
python3 -m aerosim6dof compare --a outputs/nominal_expanded/history.csv --b outputs/batch_expanded/gusted_crossrange/history.csv --out outputs/compare
python3 -m aerosim6dof trim --vehicle examples/vehicles/baseline.json --speed 120 --altitude 1000 --out outputs/trim
python3 -m aerosim6dof trim-sweep --vehicle examples/vehicles/baseline.json --speeds 90,120,150 --altitudes 0,1000 --out outputs/trim_sweep
python3 -m aerosim6dof linearize --scenario examples/scenarios/nominal_ascent.json --time 3.0 --out outputs/linearized
python3 -m aerosim6dof stability --linearization outputs/linearized/linearization.json --out outputs/stability
python3 -m aerosim6dof linear-model-report --linearization outputs/linearized/linearization.json --out outputs/linear_model_report
python3 -m aerosim6dof report --run outputs/nominal_expanded
python3 -m aerosim6dof report --run outputs/batch_expanded
```

Inspect models and build subsystem reports:

```bash
python3 -m aerosim6dof inspect-vehicle --vehicle examples/vehicles/baseline.json
python3 -m aerosim6dof inspect-aero --vehicle examples/vehicles/baseline.json
python3 -m aerosim6dof aero-report --vehicle examples/vehicles/baseline.json --out outputs/aero_report
python3 -m aerosim6dof thrust-curve-report --vehicle examples/vehicles/baseline.json --out outputs/propulsion_report
python3 -m aerosim6dof environment-report --environment examples/environments/gusted_range.json --out outputs/environment_report
python3 -m aerosim6dof sensor-report --run outputs/nominal_expanded
python3 -m aerosim6dof sweep --scenario examples/scenarios/nominal_ascent.json --set guidance.throttle=0.82,0.86 --out outputs/throttle_sweep
python3 -m aerosim6dof fault-campaign --scenario examples/scenarios/nominal_ascent.json --out outputs/fault_campaign
```

## Browser Dashboard

The web interface provides a full simulator workbench around the existing Python runtime:

- Landing page with a live replay preview in the command-center monitor
- 3D replay scene with range, coast, and night environments
- Chase, orbit, cockpit, and map camera modes
- Playback scrubber, speed controls, trail, axes, and wind overlays
- Run browser with summary metrics, event timeline, and artifact links
- Telemetry charts for flight, controls, and sensor channels
- Scenario validation, run creation, batch, Monte Carlo, sweep, fault-campaign, trim, linearization, stability, model inspection, and report workflows
- Guarded scenario editor with guided fields and raw JSON editing

Install the optional web dependencies:

```bash
python3 -m pip install -e ".[web]"
cd web
npm install
cd ..
```

Start the local dashboard:

```bash
./scripts/run_web_demo.sh
```

Then open:

```text
http://127.0.0.1:5174/
```

For a production-style local build, generate the frontend bundle and serve it through FastAPI:

```bash
cd web
npm run build
cd ..
python3 -m aerosim6dof.web.serve --host 0.0.0.0 --port 8000
```

Then open:

```text
http://127.0.0.1:8000/
```

## Outputs

Each run directory contains:

- `history.csv`: combined truth, controls, environment, aero, guidance, and sensor channels
- `truth.csv`: state, atmosphere, wind, aerodynamic, propulsion, and energy channels
- `controls.csv`: commands, achieved deflections, throttle, saturation, and failure flags
- `sensors.csv`: IMU, GPS, barometer, pitot/static, and magnetometer measurements
- `events.json`: burnout, apogee, qbar/load exceedance, actuator saturation, target crossing, ground impact, and max-altitude events
- `summary.json`: final state and envelope metrics
- `scenario_resolved.json`: scenario after inheritance and config merges
- `manifest.json`: version, run settings, sample count, and artifact inventory
- `report.html`: self-contained run report linking the SVG plots
- `plots/*.svg`: a rich set of trajectory, attitude, loads, controls, sensor, and envelope plots

Batch and Monte Carlo runs additionally write aggregate index CSV files and HTML dashboards:

- `batch_index.csv` and `batch_report.html`
- `monte_carlo_index.csv`, `monte_carlo_summary.json`, and `monte_carlo_report.html`
- `fault_campaign_index.csv`, `fault_campaign_summary.json`, and `fault_campaign_report.html`
- `sensor_report/sensor_metrics.json`, `sensor_report/sensor_metrics.csv`, and `sensor_report/sensor_report.html`

## Packaged Scenarios

The examples include nominal ascent, gusted crossrange, actuator saturation, stuck elevator, thrust misalignment, high-altitude low-density flight, noisy-sensor autopilot, GPS dropout navigation, IMU bias navigation, target intercept, engine thrust loss, high-angle-of-attack stall, waypoint navigation, and glide-return cases. Scenarios can inherit reusable vehicle and environment files from `examples/vehicles/` and `examples/environments/`.

## Project Layout

```text
aerosim6dof/
  core/          Quaternion, rotation, interpolation, integration, and unit helpers
  environment/   Atmosphere, gravity, wind, turbulence, and terrain models
  vehicle/       State, mass properties, geometry, propulsion, aero, actuators, failures
  gnc/           Guidance, autopilot, controllers, allocation, navigation, trim
  sensors/       IMU, GPS, barometer, pitot, magnetometer, radar, optical flow, horizon
  simulation/    Dynamics, events, runner, logging, Monte Carlo and fault campaigns
  analysis/      Metrics, envelopes, validation, comparison, subsystem reports
  reports/       CSV, JSON, SVG, and HTML writers
  web/           FastAPI browser API, run indexing, jobs, and artifact access
examples/
docs/
tests/
web/             React, Vite, TypeScript, and Three.js dashboard
```

## Extending

Add a scenario JSON under `examples/scenarios/`, point it at a vehicle and environment config, and override only the sections that need to change. The default models are intentionally readable: aerodynamic derivatives, thrust curves, actuator failures, wind events, sensor noise, guidance modes, event limits, and integrator choice are all scenario-configurable.

See `docs/` for model assumptions, scenario fields, vehicle modeling guidance, sensor references, output channel definitions, validation notes, and known limitations.
