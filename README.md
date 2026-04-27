# High-Fidelity Flight Vehicle Simulation

`aerosim6dof` is a compact, inspectable six-degree-of-freedom flight simulation package for early GNC, vehicle concept, mission-performance, and sensor-analysis studies. It models rigid-body translation and rotation, quaternion attitude propagation, atmosphere and gravity variation, winds and gusts, propulsion and mass depletion, aerodynamic force and moment buildup, actuator dynamics, guidance/autopilot loops, sensor measurements, event detection, and report outputs.

The core runtime uses Python 3.12 and NumPy only.

## Quick Start

```bash
cd "/Users/avipatel/Documents/New project 3/high_fidelity_flight_vehicle_sim"
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
examples/
docs/
tests/
```

## Extending

Add a scenario JSON under `examples/scenarios/`, point it at a vehicle and environment config, and override only the sections that need to change. The default models are intentionally readable: aerodynamic derivatives, thrust curves, actuator failures, wind events, sensor noise, guidance modes, event limits, and integrator choice are all scenario-configurable.

See `docs/` for model assumptions, scenario fields, vehicle modeling guidance, sensor references, output channel definitions, validation notes, and known limitations.
