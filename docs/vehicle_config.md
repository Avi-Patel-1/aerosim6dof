# Vehicle Configuration

Vehicle configs are JSON files that may inherit from a base file with `extends`. They define mass, dry mass, inertia, reference geometry, propulsion, actuators, aerodynamic derivatives, and optional aerodynamic databases.

Useful commands:

```bash
python3 -m aerosim6dof inspect-vehicle --vehicle examples/vehicles/baseline.json
python3 -m aerosim6dof config-diff --a examples/vehicles/baseline.json --b examples/vehicles/electric_uav.json
python3 -m aerosim6dof generate-scenario --name new_case --out examples/scenarios/new_case.json
```

Generated scenario templates are immediately runnable and include baseline initial state, guidance, sensors, and event limits.

