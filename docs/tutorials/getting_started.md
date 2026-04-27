# Getting Started Tutorial

1. Validate a scenario.

```bash
python3 -m aerosim6dof validate --scenario examples/scenarios/nominal_ascent.json
```

2. Run it.

```bash
python3 -m aerosim6dof run --scenario examples/scenarios/nominal_ascent.json --out outputs/tutorial_nominal
```

3. Open `outputs/tutorial_nominal/report.html`.

4. Inspect a subsystem.

```bash
python3 -m aerosim6dof aero-report --vehicle examples/vehicles/baseline.json --out outputs/tutorial_aero
```

