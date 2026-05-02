# Scenario Builder v2

Scenario Builder v2 is the guided mission-design editor in the AeroLab browser workbench. It helps users draft runnable scenario JSON without editing packaged examples by hand, while still preserving the full scenario schema for expert use.

## Purpose

- Make common scenario changes fast: duration, time step, vehicle, environment, initial state, guidance commands, sensor seed, and event limits.
- Keep browser drafts isolated under `outputs/web_runs/scenario_drafts/`.
- Keep checked-in examples under `examples/scenarios/` unchanged.
- Use the same validation and run path as the CLI and FastAPI backend.
- Avoid hiding the JSON model: guided fields are a convenience layer over scenario JSON, not a separate format.

## Design Principles

- **One scenario source:** guided edits update the same JSON shown in raw mode.
- **Guarded, not restrictive:** simple fields cover frequent edits; raw JSON remains available for unsupported fields.
- **Backend is authoritative:** browser feedback is preflight help, but the Python scenario loader decides whether a scenario is valid.
- **Drafts are disposable:** save generated drafts and runs under `outputs/web_runs/`; promote useful cases manually into `examples/scenarios/`.
- **Examples teach shape:** start from packaged scenarios such as `nominal_ascent`, `waypoint_navigation`, `gps_dropout_navigation`, and `target_intercept`.

## Builder Sections

### Mission Profile

Controls core run setup:

- `name`: scenario/run identity.
- `duration` and `dt`: simulation length and integration step.
- `integrator`: numerical integration method.
- `vehicle_config`: reusable vehicle file from `examples/vehicles/`.
- `environment_config`: reusable environment file from `examples/environments/`.
- Initial altitude, forward speed, and pitch: mapped into `initial.position_m`, `initial.velocity_mps`, and `initial.euler_deg`.
- Throttle and heading: mapped into `guidance`.
- Sensor seed: mapped into `sensors.seed`.
- Qbar and load limits: mapped into `events.qbar_limit_pa` and `events.load_limit_g`.

Use this section for nominal ascent, altitude-hold, waypoint, and terrain/AGL cases. The preset rail can create calm, gusty, high-altitude, terrain, sensor-fault, and intercept drafts from safe defaults.

### Vehicle

Controls the vehicle reference and high-level command assumptions:

- `vehicle_config`: reusable vehicle file from `examples/vehicles/`.
- Throttle command.
- Qbar and load-factor limits that protect the run envelope.

### Environment

Controls range and atmosphere assumptions:

- `environment_config`: reusable environment file from `examples/environments/`.
- Inline wind vector and turbulence intensity overrides for quick sensitivity checks.

### Initial State

Controls launch/entry state:

- Downrange, crossrange, and altitude.
- Forward and vertical velocity.
- Pitch and heading/yaw.

### GNC

Controls the guidance mode and command set:

- Supported modes include `pitch_program`, `altitude_hold`, `waypoint`, `target_intercept`, `proportional_navigation`, `heading_hold`, and `open_loop`.
- Heading, pitch, throttle, and altitude commands are exposed as guarded controls.

### Sensors

Controls basic sensor model settings:

- Sensor seed.
- IMU, GPS, pitot, and radar-altimeter rates/noise/dropout settings.

### Faults

Controls injected sensor failures:

- Faults are written to `sensors.faults`.
- Supported first-pass types are `dropout`, `bias`, `bias_jump`, and `scale`.
- Each fault includes sensor, start time, and end time.

### Targets

Controls moving engagement or navigation objects:

- Target `id` and `role` (`primary`, `decoy`, or `waypoint`).
- Initial position components, including altitude.
- X velocity.

Targets are written to the top-level `targets` array. Existing examples use this for `target_intercept`.

### Interceptors

Controls kinematic interceptor objects:

- Interceptor `id`.
- `target_id` link to a target.
- Launch time.
- Max speed, max acceleration, and proximity fuze radius.

Interceptors are written to the top-level `interceptors` array and produce `interceptors.csv` plus engagement artifacts when run.

### Raw JSON

Raw JSON is expert mode. Use it for fields not exposed by guided controls, including:

- Full initial position/velocity/body rates.
- `wind`, inline `environment`, terrain, and ground-contact overrides.
- Guidance modes such as `altitude_hold`, `waypoint`, `target_intercept`, and `proportional_navigation`.
- Autopilot tuning.
- Detailed sensor models, rates, dropout, bias, radar altimeter, optical flow, and fault arrays.
- Vehicle overrides.
- Event thresholds such as `target_threshold_m`.

Switching modes should not change the schema. The raw JSON is what gets validated, saved, and run.

## Validation Behavior

The builder can show guardrails and "needs attention" status, but these are user-facing preflight signals. They are not the final authority.

Hard validation happens through `POST /api/validate`, which loads the draft through the Python `Scenario` path used by the CLI. The same checks reject invalid command-line scenarios, including:

- Non-finite or non-positive `dt` and `duration`.
- More than 500,000 time steps.
- Unsupported integrator names.
- Invalid vector lengths for initial state, target, or interceptor vectors.
- Invalid mass/dry-mass relationships.
- Throttle outside `[0, 1]`.
- Non-positive event limits.
- Invalid sensor rates or sensor fault definitions.
- Malformed target/interceptor arrays.

Use browser warnings to catch likely mistakes early. Treat backend validation errors as blocking until fixed.

## Example Workflows

### Nominal Run

1. Open the browser workbench and go to **Editor**.
2. Select `nominal_ascent` as the base.
3. Adjust `duration`, `dt`, throttle, heading, or limits in **Mission Profile**.
4. Click **Validate**.
5. Click **Run Draft**.
6. Review replay, telemetry, `summary.json`, and `report.html`.

CLI equivalent:

```bash
python3 -m aerosim6dof validate --scenario examples/scenarios/nominal_ascent.json
python3 -m aerosim6dof run --scenario examples/scenarios/nominal_ascent.json --out outputs/nominal_builder_check
```

### Terrain/AGL Mission

1. Start from `glide_return`, `waypoint_navigation`, or another low-altitude case.
2. In guided mode, select an environment with terrain if available, such as `terrain_range`.
3. Use raw JSON for terrain-specific overrides if needed:

```json
"environment_config": "../environments/terrain_range.json",
"sensors": {
  "seed": 42,
  "radar_altimeter": {
    "rate_hz": 20.0,
    "max_range_m": 1800.0
  }
}
```

4. Validate and run.
5. Inspect `altitude_agl_m`, `terrain_elevation_m`, `radar_agl_m`, ground-contact events, and the `28_agl_terrain.svg` plot.

CLI checks:

```bash
python3 -m aerosim6dof environment-report --environment examples/environments/terrain_range.json --out outputs/environment_terrain_check
python3 -m aerosim6dof run --scenario examples/scenarios/glide_return.json --out outputs/glide_return_check
```

### Sensor-Fault Run

1. Start from `gps_dropout_navigation` or `sensor_noise_autopilot`.
2. Use guided mode for duration, vehicle, environment, and seed.
3. Switch to raw JSON to edit detailed sensor faults:

```json
"sensors": {
  "seed": 261,
  "gps": {
    "rate_hz": 3.0,
    "position_noise_std_m": 3.0
  },
  "faults": [
    {
      "sensor": "gps",
      "type": "dropout",
      "start_s": 7.0,
      "end_s": 11.0
    }
  ]
}
```

4. Validate and run.
5. Review `sensors.csv`, the telemetry sensor channels, and `sensor-report`.

CLI equivalent:

```bash
python3 -m aerosim6dof validate --scenario examples/scenarios/gps_dropout_navigation.json
python3 -m aerosim6dof run --scenario examples/scenarios/gps_dropout_navigation.json --out outputs/gps_dropout_check
python3 -m aerosim6dof sensor-report --run outputs/gps_dropout_check
```

### Intercept Mission

1. Start from `target_intercept`.
2. Click the **Intercept** preset or add targets and interceptors manually.
3. Confirm each interceptor `target_id` matches a target `id`.
4. Use raw JSON for fields not exposed by the cards, such as target Y/Z velocity or `events.target_threshold_m`.
5. Validate and run.
6. Review target labels, miss-distance markers, `targets.csv`, `interceptors.csv`, and `engagement_report.html`.

CLI equivalent:

```bash
python3 -m aerosim6dof validate --scenario examples/scenarios/target_intercept.json
python3 -m aerosim6dof run --scenario examples/scenarios/target_intercept.json --out outputs/target_intercept_check
python3 -m aerosim6dof engagement-report --run outputs/target_intercept_check
```

## Testing Checklist

### Local Web

- Install web extras: `python3 -m pip install -e ".[web]"`.
- Install frontend dependencies: `cd web && npm install`.
- Start the demo: `scripts/run_web_demo.sh`.
- Open the printed Vite URL, usually `http://127.0.0.1:5174/`.
- In **Editor**, load `nominal_ascent`, validate, save a draft, and run it.
- Confirm drafts are written under `outputs/web_runs/scenario_drafts/`.
- Confirm generated runs appear in the run selector and Reports tab.
- Repeat with `target_intercept` and confirm engagement artifacts are linked.
- Try invalid JSON in raw mode and confirm validation reports a blocking error.

### CLI/API Parity

- Run unit tests: `python3 -m unittest discover -s tests`.
- Validate representative examples:

```bash
python3 -m aerosim6dof validate --scenario examples/scenarios/nominal_ascent.json
python3 -m aerosim6dof validate --scenario examples/scenarios/gps_dropout_navigation.json
python3 -m aerosim6dof validate --scenario examples/scenarios/target_intercept.json
```

- Run at least one draft-equivalent scenario through the CLI.
- Generate `sensor-report` for a sensor-fault run.
- Generate `engagement-report` for an intercept run.
- Check `history.csv`, `truth.csv`, `controls.csv`, `sensors.csv`, `events.json`, `summary.json`, and `scenario_resolved.json`.

## TODOs

- Add guided controls for full 3-axis initial position, velocity, attitude, and body rates.
- Add explicit guidance-mode controls for pitch program, altitude hold, waypoint, target intercept, and proportional navigation.
- Add terrain and ground-contact controls in guided mode.
- Add detailed sensor cards for GPS, IMU, barometer, radar altimeter, optical flow, and faults.
- Add target/interceptor controls for all vector components.
- Add client-side warning text that maps common validation errors to the affected field.
- Add a promote-to-example workflow with review safeguards.
- Add regression fixtures for saved browser drafts.
