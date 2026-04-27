# Faults

Current fault support includes stuck actuators, delayed commands, surface effectiveness degradation, propulsion shutdown intervals, thrust misalignment, engine restart/no-restart behavior, sensor dropout, sensor bias jumps, pitot blockage, noisy navigation, qbar/load exceedance events, ground impact, apogee, burnout, and target crossing.

Fault scenarios in `examples/scenarios/` include stuck elevator, thrust misalignment, engine thrust loss, actuator saturation, noisy-sensor autopilot, GPS dropout navigation, and IMU bias navigation cases.

## Sensor Fault Timeline

Sensor faults live under `sensors.faults` and are active between `start_s` and `end_s`. Supported fault types are `dropout`, `bias_jump`, `bias`, and `scale`. A single fault can target one sensor with `sensor` or several with `sensors`.

## Fault Campaigns

Run the built-in fault library against a baseline scenario:

```bash
python3 -m aerosim6dof fault-campaign --scenario examples/scenarios/nominal_ascent.json --out outputs/fault_campaign
```

Limit the campaign to specific cases:

```bash
python3 -m aerosim6dof fault-campaign --scenario examples/scenarios/nominal_ascent.json --fault gps_dropout --fault thrust_loss --out outputs/fault_campaign_subset
```

The campaign writes each run directory, `fault_campaign_index.csv`, `fault_campaign_summary.json`, and `fault_campaign_report.html`.
