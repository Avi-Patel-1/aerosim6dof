# Sensor Models

The sensor suite generates logs separate from truth channels and supports sample-rate mismatch.

## IMU

The IMU reports body acceleration and angular rates with noise, bias, random walk, scale factor, misalignment, saturation, and fault-injected bias jumps. It logs validity, individual axes, acceleration norm, and gyro norm.

## GPS

GPS reports position and velocity with configurable noise, update rate, dropout probability, fixed bias, latency, velocity bias, and sinusoidal multipath. Latency is modeled by retaining a truth buffer and sampling an older position/velocity pair.

## Barometer

The barometer reports altitude with noise, bias, drift rate, saturation, dropout, and externally injected bias.

## Pitot/Static

The pitot model reports measured airspeed and dynamic pressure. It supports additive bias, partial blockage, configurable qbar noise fraction, and simple subsonic compressibility correction.

## Magnetometer

The magnetometer reports heading and body-frame magnetic vector components. It includes simplified field strength, inclination, declination, hard-iron offset, soft-iron scaling/matrix, noise, saturation, and dropout.

## Radar Altimeter

The radar altimeter reports range-to-ground with max range, bias, noise, dropout probability, and validity flag. The main flight report logs it in `sensors.csv`; `sensor-report` compares it against altitude for flat-terrain runs.

## Optical Flow

The optical-flow sensor estimates small-angle image motion from body-frame translational velocity and height above ground. It includes altitude operating limits, rate saturation, quality, noise, and dropout.

## Horizon Sensor

The horizon sensor reports roll and pitch with noise, bias, field-of-view limits, and dropout. It is useful as a lightweight attitude reference for navigation studies.

## Sensor Faults

Scenario files can define `sensors.faults` entries:

```json
{
  "sensor": "gps",
  "type": "dropout",
  "start_s": 7.0,
  "end_s": 11.0
}
```

Bias faults use the same schedule fields plus sensor-specific keys such as `accel_bias_mps2`, `gyro_bias_rps`, `position_bias_m`, `bias_m`, or `bias_mps`.

## Sensor Reports

Run:

```bash
python3 -m aerosim6dof sensor-report --run outputs/nominal_expanded
```

The report writes `sensor_metrics.json`, `sensor_metrics.csv`, SVG plots, and `sensor_report.html`. Metrics include valid fractions, dropout transitions, GPS position/velocity RMSE, barometer altitude RMSE, pitot airspeed RMSE, radar range RMSE for flat terrain, magnetometer heading RMSE, and horizon attitude RMSE.
