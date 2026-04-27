# Aerodynamics

The aerodynamic model supports derivative-based coefficients and JSON aerodynamic databases.

Features:

- Mach-scheduled derivative tables, such as `cl_alpha_by_mach`
- Alpha/Mach coefficient database interpolation for `cd`, `cl`, `cy`, `cm`, `cn`, and `cl_roll`
- Prandtl-Glauert and Karman-Tsien compressibility correction options
- Stall and post-stall lift/drag approximation
- Roll, pitch, yaw damping derivatives
- Cross-coupling derivative hooks
- Deterministic coefficient scale/bias uncertainty fields

CLI tools:

```bash
python3 -m aerosim6dof inspect-aero --vehicle examples/vehicles/baseline.json
python3 -m aerosim6dof aero-sweep --vehicle examples/vehicles/baseline.json --mach 0.3,0.7 --alpha=-5,5 --out outputs/aero_sweep
python3 -m aerosim6dof aero-report --vehicle examples/vehicles/baseline.json --out outputs/aero_report
```

