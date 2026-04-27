# Output Reference

Each run writes `history.csv`, `truth.csv`, `controls.csv`, `sensors.csv`, `events.json`, `summary.json`, `scenario_resolved.json`, `manifest.json`, `report.html`, and SVG plots.

Important truth channels include position, velocity, speed, mass, euler attitude, body rates, alpha, beta, Mach, qbar, airspeed, load factor, atmosphere, wind, thrust, energy, and guidance commands.

Important control channels include command deflections, achieved deflections, throttle, saturation flags, failure flags, raw actuator positions, and effective actuator positions.

Important sensor channels include IMU acceleration, gyro rates, GPS position and velocity, GPS validity, barometric altitude, pitot airspeed and qbar, and magnetometer heading.

The HTML report is intentionally static so it can be opened directly in a browser from a run directory.

`scenario_resolved.json` records the scenario after inheritance and vehicle/environment merges. `manifest.json` records simulator version, generation time, timestep, duration, sample count, and the artifact inventory.

Batch runs write `batch_summary.json`, `batch_index.csv`, and `batch_report.html`. The dashboard links to each scenario report and summarizes maximum altitude, speed, load factor, duration, event counts, and final altitude.

Monte Carlo runs write `monte_carlo_summary.json`, `monte_carlo_index.csv`, `monte_carlo_report.html`, and per-sample run directories. The summary includes mean and standard deviation for final altitude, maximum qbar, and maximum load factor.
