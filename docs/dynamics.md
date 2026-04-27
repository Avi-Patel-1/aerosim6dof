# Dynamics

The simulation state includes inertial position and velocity, quaternion attitude, body rates, and mass. The dynamics layer accumulates aerodynamic force/moment, propulsion force/moment, and altitude-dependent gravity.

Supported fixed-step integrators:

- `euler`
- `semi_implicit_euler`
- `rk2`
- `rk4`
- `adaptive_rk45`

The adaptive integrator uses deterministic RK4 step doubling as an RK45-like embedded error estimate. It supports step rejection, minimum step handling, and a normalized error metric while preserving the scenario-level output timestep.

Quaternion normalization is applied after each packed-state propagation. Run manifests record the integrator, timestep, duration, sample count, and output inventory.

