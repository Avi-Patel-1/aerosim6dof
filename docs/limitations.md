# Limitations

This package is intended for concept studies, controller smoke tests, mission-level trades, and integration prototyping.

Known limitations:

- Aerodynamics are derivative-based unless replaced with project-specific tables.
- The atmosphere does not model humidity, weather fronts, or Earth rotation.
- Terrain is planar.
- The sensor suite is useful for estimator interface work but is not a full hardware error model.
- The autopilot is generic and should be retuned for any real vehicle.
- Structural dynamics, slosh, aeroelasticity, detailed propulsion transients, and plume interactions are outside the default model.
- Numerical stability depends on timestep, vehicle derivatives, and controller gains.

