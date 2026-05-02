# Realistic Physics v1 Foundation

This package adds standalone realism helpers in `aerosim6dof.physics.realism`.
They do not change the integrator, runner, dynamics, vehicle modules, sensor
modules, or CSV output formats. Each helper is deterministic unless the caller
passes a NumPy random generator for sensor bias random walk.

## Included Helpers

- `layered_atmosphere`: hydrostatic piecewise atmosphere with post-layer
  temperature, pressure, and density adjustments.
- `power_law_wind_profile`, `log_wind_profile`, `turbulence_profile`, and
  `WindShearTurbulenceProfile`: wind shear and turbulence envelope lookup.
- `engine_spool_step` and `EngineSpool`: first-order engine throttle/spool
  transient with optional rate limiting.
- `FuelMassInertiaModel`: fuel burn-down mass clamp and linear inertia
  interpolation between wet and dry states.
- `ActuatorCommandShaper`: scalar command delay, deadband, saturation, backlash,
  and rate limiting.
- `LatencyBuffer` and `SensorLatencyBias`: interpolated sensor latency plus
  additive bias drift/random walk.

## Defensive Behavior

- Negative altitude is clamped to sea level for atmosphere lookup.
- Negative time steps, negative scales, invalid layer ordering, invalid matrix
  shapes, and out-of-order latency samples raise `ValueError`.
- Burn-down mass is clamped between dry and initial mass.
- Engine and actuator commands are clipped to configured command limits.
- Sensor random walk is only applied when the caller passes an RNG.

## Later Integration Points

1. Atmosphere:
   In `aerosim6dof/environment/atmosphere.py`, replace or wrap
   `isa_atmosphere(altitude_m)` with `layered_atmosphere(...)`, then map
   `density_kgpm3`, `pressure_pa`, `temperature_k`, and `speed_of_sound_mps`
   onto the existing `AtmosphereState` fields.

2. Wind:
   In `aerosim6dof/environment/wind.py`, use `WindShearTurbulenceProfile.sample`
   inside `WindModel._shear` or as a precomputed environment helper. Keep the
   returned steady wind and turbulence sigma separate so the existing turbulence
   sampler can continue to own random draws.

3. Propulsion:
   In `aerosim6dof/vehicle/propulsion.py`, replace `_lagged_throttle` internals
   with `EngineSpool` or call `engine_spool_step(self.actual_throttle, cmd, dt)`.
   Continue to compute thrust, moments, and mass flow in the existing propulsion
   model.

4. Mass properties:
   In `aerosim6dof/vehicle/mass_properties.py`, construct
   `FuelMassInertiaModel` from the vehicle wet/dry mass and inertia config.
   Use `state_for_mass(mass_kg).inertia_kgm2` as the source for current inertia.

5. Actuators:
   In `aerosim6dof/vehicle/actuators.py`, put `ActuatorCommandShaper` ahead of
   the existing surface effectiveness/failure logic. Existing telemetry flags
   can use `ActuatorCommandSample.saturated` and `.rate_limited` without changing
   CSV column names unless new columns are intentionally added.

6. Sensors:
   In `aerosim6dof/sensors/*`, use `LatencyBuffer` for truth-history lookup and
   `SensorLatencyBias` for shared latency/bias behavior. Keep each sensor's
   output dictionary keys unchanged unless a later schema migration is planned.

## Verification

Focused coverage lives in `tests/test_realistic_physics.py` and exercises:

- atmosphere sanity and invalid layer behavior;
- wind/turbulence monotonic trends and invalid profile inputs;
- engine spool lag and rate limiting;
- burn-down clamping and inertia interpolation;
- actuator delay, deadband, backlash, and monotonic time checks;
- latency interpolation and deterministic bias drift.
