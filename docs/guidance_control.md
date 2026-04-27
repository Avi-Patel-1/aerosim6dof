# Guidance Control

Guidance modes produce roll, pitch, heading, throttle, and target-distance commands. The autopilot maps those commands to elevator, aileron, rudder, and throttle with scheduled PID loops and surface allocation.

Implemented guidance modes include fixed pitch, pitch program, heading hold, altitude hold, waypoint, target intercept, and proportional-navigation-inspired guidance.

Control utilities now include PID loops, anti-windup behavior, dynamic-pressure scheduling, allocation limits, controllability checks, and discrete LQR synthesis.

