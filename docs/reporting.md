# Reporting

Run reports are static HTML documents with SVG plots and JSON/CSV artifacts. Batch, Monte Carlo, parameter-sweep, fault-campaign, sensor, aero, propulsion, environment, trim-sweep, and stability reports follow the same dependency-free pattern.

Report writers are intentionally simple so output directories can be archived, reviewed, and opened without a server.

## Report Commands

```bash
python3 -m aerosim6dof report --run outputs/nominal_expanded
python3 -m aerosim6dof sensor-report --run outputs/nominal_expanded
python3 -m aerosim6dof aero-report --vehicle examples/vehicles/baseline.json --out outputs/aero_report
python3 -m aerosim6dof thrust-curve-report --vehicle examples/vehicles/baseline.json --out outputs/propulsion_report
python3 -m aerosim6dof environment-report --environment examples/environments/gusted_range.json --out outputs/environment_report
python3 -m aerosim6dof stability --linearization outputs/linearized/linearization.json --out outputs/stability
```

Each report directory includes machine-readable JSON, CSV indexes or metrics, and SVG plots. This keeps the report useful both for visual inspection and for regression tooling.
