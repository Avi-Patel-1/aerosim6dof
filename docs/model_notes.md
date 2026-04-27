# Model Notes

## Frames

The inertial frame uses `x` downrange, `y` crossrange, and `z` altitude-up coordinates. The body frame uses `x` forward, `y` right, and `z` up. Reported pitch is positive nose-up. Internally, quaternion propagation remains right-handed; the euler conversion layer handles the z-up pitch convention.

## State

```text
r_i = [x, y, z]
v_i = [vx, vy, vz]
q_b_to_i = [qw, qx, qy, qz]
w_b = [p, q, r]
m = vehicle mass
```

The quaternion maps body-frame vectors into the inertial frame and is normalized after every integration step.

## Translational Dynamics

```text
r_dot = v
v_dot = R_bi F_b / m + g_i
```

The body-force sum includes aerodynamic force and propulsion. Gravity is altitude-dependent and points in negative inertial `z`. Wind is subtracted from inertial velocity before computing body-frame air-relative velocity.

## Rotational Dynamics

```text
w_dot = I^-1 (M_b - w x Iw)
q_dot = 0.5 Omega(w) q
```

Moments include aerodynamic static stability, rate damping, control derivatives, thrust offset, thrust misalignment, and nozzle-cant moment. Inertia varies linearly between loaded and dry inertia as propellant burns.

## Atmosphere and Gravity

The atmosphere is ISA-like with troposphere lapse-rate behavior to 11 km and isothermal stratosphere extension above that altitude. Gravity follows an inverse-square altitude variation.

## Aerodynamics

The default aerodynamic model computes drag, lift, side force, roll, pitch, and yaw coefficients from angle of attack, sideslip, angular rates, control deflections, Mach effects, and reference geometry. A simple one-dimensional table hook supports replacing selected coefficient terms from scenario JSON.

## Integration

The runner supports semi-implicit Euler, explicit Euler, and RK4. Semi-implicit Euler is the default for robust scenario sweeps. RK4 is available when smoother deterministic propagation is useful.

