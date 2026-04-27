# Scenario Reference

Scenario files are JSON objects. They may include:

- `extends`: path to a base scenario JSON
- `vehicle_config`: path to a reusable vehicle JSON
- `environment_config`: path to a reusable environment JSON
- `name`, `dt`, `duration`, `integrator`
- `initial`: `position_m`, `velocity_mps`, `euler_deg`, `body_rates_dps`
- `vehicle`: scenario-specific vehicle overrides
- `environment`: terrain and other environment overrides
- `wind`: steady wind, shear, sinusoidal gust, discrete gust, and turbulence
- `guidance`: mode, commands, targets, throttle, and navigation source
- `autopilot`: PID overrides and scheduling parameters
- `sensors`: noise, sample rates, dropout, and seed
- `events`: qbar, load, and target thresholds

Paths are resolved relative to the scenario file first, then relative to the repository root.

Supported integrators are `semi_implicit_euler`, `euler`, and `rk4`.

Supported packaged guidance modes are `fixed_pitch`, `pitch_program`, `heading_hold`, `altitude_hold`, `waypoint`, `target_intercept`, and `proportional_navigation`.

## Monte Carlo Inputs

The `monte-carlo` CLI command starts from a validated scenario and applies repeatable dispersions before each run. Current built-in dispersions are:

- `--mass-sigma-kg`: one-sigma loaded mass perturbation, clamped above dry mass
- `--wind-sigma-mps`: one-sigma steady-wind perturbation applied independently on each axis
- `--seed`: base seed used for scenario perturbations and sensor seeds

Each sample is written to its own run directory and summarized in `monte_carlo_index.csv`.
