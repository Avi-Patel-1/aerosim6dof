# Propulsion

The propulsion model supports solid-style thrust curves, liquid-style throttle lag, electric thrust falloff with airspeed, thrust misalignment, nozzle-cant moment, ignition delay, shutdown intervals, and restart policy flags.

Outputs include thrust, mass flow, actual throttle, and propulsion health state. Thrust-curve reports write CSV, JSON, SVG, and static HTML artifacts.

CLI tools:

```bash
python3 -m aerosim6dof inspect-propulsion --vehicle examples/vehicles/baseline.json
python3 -m aerosim6dof thrust-curve-report --vehicle examples/vehicles/baseline.json --out outputs/propulsion_report
```

