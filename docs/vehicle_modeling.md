# Vehicle Modeling

Vehicle configs define mass properties, reference geometry, propulsion, actuators, and aerodynamic derivatives.

## Mass and Inertia

`mass_kg` and `dry_mass_kg` define propellant capacity. `inertia_kgm2` and optional `dry_inertia_kgm2` are interpolated as mass depletes.

## Propulsion

The propulsion model supports constant thrust, JSON thrust curves, throttle limits, burn time, dry-mass cutoff, thrust offset, thrust misalignment, and nozzle-cant moments.

## Aerodynamics

The default coefficient model is derivative-based and intentionally transparent. Coefficients include base drag, alpha/beta drag, lift slope, side-force slope, pitch/yaw/roll static terms, rate damping, control derivatives, and Mach drag rise.

## Actuators

Surface actuators include position limits, rate limits, first-order lag, deadband, bias, stuck failures, command delay, and effectiveness degradation. `controls.csv` logs both commanded and achieved deflections plus saturation and failure flags.

