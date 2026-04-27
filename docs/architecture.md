# Architecture

The package is organized around small modules with explicit data flow:

1. `scenario.py` loads scenario JSON, applies `extends`, merges vehicle and environment configs, and validates common mistakes.
2. `simulation.runner` builds the vehicle, environment, GNC, actuator, sensor, terrain, and dynamics components.
3. At each step, the runner samples wind, computes guidance and autopilot commands, advances actuators, evaluates rigid-body dynamics, samples sensors, logs rows, and checks events.
4. Reports are written through dependency-free CSV, JSON, SVG, and HTML writers.

The public API remains `Scenario.from_file(...)` and `run_scenario(...)` through `aerosim6dof.sim`, so older scripts can keep importing from the original module.

## Main Extension Points

- Replace `vehicle.aerodynamics.AerodynamicModel` for CFD or wind-tunnel tables.
- Replace `vehicle.propulsion.PropulsionModel` for motor-specific thrust and mass curves.
- Add guidance modes in `gnc.guidance.GuidanceModel`.
- Add estimator integration in `gnc.navigation_hooks.NavigationHook`.
- Add output metrics in `analysis.metrics` or new plot definitions in `simulation.runner._generate_plots`.

