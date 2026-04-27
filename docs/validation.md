# Validation

The test suite covers quaternion normalization and transforms, atmosphere and gravity behavior, wind and turbulence, actuator dynamics and failures, propulsion cutoff, aerodynamic coefficient sanity, scenario validation, run artifact generation, event logging, sensor sampling, report generation, CLI smoke paths, trim, and linearization.

Run:

```bash
python3 -m unittest discover -s tests
```

Recommended smoke commands:

```bash
python3 -m aerosim6dof validate --scenario examples/scenarios/nominal_ascent.json
python3 -m aerosim6dof run --scenario examples/scenarios/nominal_ascent.json --out outputs/nominal_expanded
python3 -m aerosim6dof batch --scenarios examples/scenarios --out outputs/batch_expanded
python3 -m aerosim6dof report --run outputs/nominal_expanded
python3 -m aerosim6dof monte-carlo --scenario examples/scenarios/nominal_ascent.json --samples 3 --seed 77 --mass-sigma-kg 0.2 --out outputs/monte_carlo_nominal
```

Validation is focused on numerical sanity and artifact integrity. It is not a certification package.
