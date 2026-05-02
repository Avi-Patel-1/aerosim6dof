# Missile Dynamics V1

`aerosim6dof.simulation.missile_dynamics` provides the production missile-runtime path used by `InterceptorSuite` when an interceptor explicitly opts in with `"dynamics_model": "missile_dynamics_v1"` or `"model": "missile"`. Interceptors without that opt-in continue to use the legacy kinematic model.

## Scope

- Seeker measurement from missile and target inertial position/velocity.
- Range and field-of-view validity gates.
- 3-D proportional-navigation acceleration command.
- Solid-motor style thrust profile with ignition delay, spool-up, mass flow, and burnout.
- Vector control actuator with acceleration magnitude and rate limits.
- Proximity fuze with arming time and self-destruct timeout.
- `step_missile(...)` helper returning the next `MissileState` and flat telemetry.

## Main API

```python
from aerosim6dof.simulation.missile_dynamics import (
    MissileDynamicsConfig,
    MissileState,
    TargetState,
    step_missile,
)

config = MissileDynamicsConfig.from_dict(optional_missile_config)
state = MissileState(time_s=0.0, position_m=pos, velocity_mps=vel, mass_kg=54.0)
target = TargetState(position_m=target_pos, velocity_mps=target_vel, target_id="incoming")
result = step_missile(state, target, dt=0.02, config=config)
state = result.state
telemetry = result.telemetry
```

Lower-level primitives are available as `measure_seeker`, `proportional_navigation`, `sample_motor`, `rate_limit_vector`, and `evaluate_fuze`.

## Scenario Compatibility

`examples/scenarios/missile_intercept_demo.json` keeps the existing scenario shape and adds an optional top-level `missile` block. `InterceptorSuite.from_scenario(...)` reads that block as the shared missile configuration seed for interceptor entries with `"dynamics_model": "missile_dynamics_v1"` or `"model": "missile"`.

The existing `interceptors` list remains the runtime owner. Missile-mode entries can override shared settings with a nested `missile` block or with direct missile fields such as `seeker`, `guidance`, `motor`, `actuator`, `fuze`, `dry_mass_kg`, or `gravity_mps2`. Existing kinematic fields such as `initial_position_m`, `initial_velocity_mps`, `launch_time_s`, `target_id`, and `proximity_fuze_m` still apply.

## Telemetry

`step_missile` returns flat telemetry fields intended to be easy to merge into existing CSV/report writers:

- `missile_*`: position, velocity, speed, mass, and total acceleration.
- `seeker_*`: validity, status, range, range rate, closing speed, and aspect.
- `guidance_*`: PN command validity, status, and command magnitude.
- `control_*`: achieved acceleration plus saturation/rate-limit flags.
- `motor_*`: thrust, mass flow, spool fraction, and phase.
- `fuze_*`: arming/fuzed flags, status, and closest range.

When merged into interceptor runtime rows, the integrated path adds these flat columns:

- `missile_mode`
- `seeker_valid`
- `missile_motor_thrust_n`
- `missile_motor_mass_flow_kgps`
- `missile_commanded_accel_mps2`
- `missile_lateral_accel_mps2`
- `missile_closing_speed_mps`
- `missile_fuze_armed`
- `missile_fuzed`

## Integration Notes

- The primitive uses inertial vectors and does not require aircraft attitude.
- Thrust is applied along current missile velocity, falling back to seeker boresight at low speed.
- Guidance acceleration is lateral PN: `N * closing_speed * (los_rate x los_unit)`.
- Mass is reduced by motor mass flow and clamped to `dry_mass_kg`.
- The step integrator is semi-implicit Euler for deterministic small-step behavior.
