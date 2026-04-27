# Guidance and Control

Guidance produces roll, pitch, heading, throttle, and target-distance commands. The autopilot converts those commands into elevator, aileron, rudder, and throttle using PID loops and simple dynamic-pressure gain scheduling.

## Guidance Modes

- `fixed_pitch`: constant pitch and heading command
- `pitch_program`: time-based pitch schedule
- `heading_hold`: heading command with constant pitch
- `altitude_hold`: pitch command from altitude error
- `waypoint` and `target_intercept`: heading and pitch commands toward a target point
- `proportional_navigation`: target-intercept variant with closing-speed throttle bias

## Autopilot

The autopilot includes pitch, yaw, and roll PID loops, command limiting, integrator anti-windup, and control allocation. It is designed as a smoke-test controller, not a tuned production flight controller.

## Trim and Linearization

The `trim` command searches alpha/elevator combinations for approximate steady flight at a requested speed and altitude. The `linearize` command exports numerical A/B matrices around a propagated scenario state.

