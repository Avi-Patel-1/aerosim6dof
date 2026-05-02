import math
import unittest

import numpy as np

from aerosim6dof.physics import (
    ActuatorCommandShaper,
    AtmosphereLayer,
    EngineSpool,
    FuelMassInertiaModel,
    LatencyBuffer,
    SensorLatencyBias,
    WindShearTurbulenceProfile,
    engine_spool_step,
    layered_atmosphere,
    log_wind_profile,
    power_law_wind_profile,
    turbulence_profile,
)


class RealisticPhysicsTests(unittest.TestCase):
    def test_layered_atmosphere_is_continuous_and_adjustable(self):
        sea_level = layered_atmosphere(0.0)
        high = layered_atmosphere(10_000.0)
        warm = layered_atmosphere(0.0, temperature_offset_k=10.0)

        self.assertAlmostEqual(sea_level.pressure_pa, 101_325.0, delta=1.0)
        self.assertAlmostEqual(sea_level.density_kgpm3, 1.225, delta=0.01)
        self.assertGreater(sea_level.density_kgpm3, high.density_kgpm3)
        self.assertGreater(warm.speed_of_sound_mps, sea_level.speed_of_sound_mps)
        self.assertLess(warm.density_kgpm3, sea_level.density_kgpm3)

        lower = layered_atmosphere(-100.0)
        self.assertEqual(lower.altitude_m, 0.0)

    def test_layered_atmosphere_rejects_bad_inputs(self):
        with self.assertRaises(ValueError):
            layered_atmosphere(0.0, pressure_scale=-1.0)
        with self.assertRaises(ValueError):
            layered_atmosphere(0.0, layers=[AtmosphereLayer(100.0, 0.0)])
        with self.assertRaises(ValueError):
            layered_atmosphere(0.0, layers=[AtmosphereLayer(0.0, 0.0), AtmosphereLayer(0.0, 0.0)])

    def test_wind_shear_and_turbulence_profiles(self):
        low = power_law_wind_profile(10.0, [10.0, 0.0, 0.0])
        high = power_law_wind_profile(160.0, [10.0, 0.0, 0.0])
        log_high = log_wind_profile(40.0, [8.0, 1.0, 0.0])
        profile = WindShearTurbulenceProfile([12.0, 0.0, 0.0]).sample(200.0)
        turb_low = turbulence_profile(0.0)
        turb_high = turbulence_profile(5000.0)

        self.assertGreater(high[0], low[0])
        self.assertEqual(log_high.shape, (3,))
        self.assertEqual(profile.steady_wind_mps.shape, (3,))
        self.assertTrue(np.all(turb_low.sigma_mps >= turb_high.sigma_mps))
        self.assertTrue(np.all(turb_high.length_scale_m >= turb_low.length_scale_m))

        with self.assertRaises(ValueError):
            log_wind_profile(1.0, [1.0, 0.0, 0.0], reference_altitude_m=0.01, roughness_length_m=0.03)
        with self.assertRaises(ValueError):
            turbulence_profile(10.0, reference_sigma_mps=[1.0, -1.0, 0.0])

    def test_engine_spool_transient_and_rate_limit(self):
        sample = engine_spool_step(0.0, 1.0, 0.1, spool_up_tau_s=1.0)
        self.assertGreater(sample.actual, 0.0)
        self.assertLess(sample.actual, 1.0)
        self.assertFalse(sample.rate_limited)

        limited = engine_spool_step(0.0, 1.0, 0.2, spool_up_tau_s=0.01, rate_limit_per_s=0.5)
        self.assertAlmostEqual(limited.actual, 0.1)
        self.assertTrue(limited.rate_limited)

        spool = EngineSpool(initial=1.0, spool_down_tau_s=0.2)
        down = spool.step(0.0, 0.1)
        self.assertLess(down.actual, 1.0)
        self.assertEqual(spool.actual, down.actual)

        with self.assertRaises(ValueError):
            engine_spool_step(0.0, 1.0, -0.1)

    def test_fuel_mass_inertia_burn_down_clamps_at_dry_mass(self):
        model = FuelMassInertiaModel(
            initial_mass_kg=10.0,
            dry_mass_kg=6.0,
            initial_inertia_kgm2=np.diag([4.0, 5.0, 6.0]),
            dry_inertia_kgm2=np.diag([2.0, 3.0, 4.0]),
        )

        sample = model.step(current_mass_kg=10.0, mass_flow_kgps=2.0, dt=1.0)
        self.assertAlmostEqual(sample.mass_kg, 8.0)
        self.assertAlmostEqual(sample.fuel_fraction, 0.5)
        self.assertTrue(np.allclose(np.diag(sample.inertia_kgm2), [3.0, 4.0, 5.0]))

        dry = model.step(current_mass_kg=7.0, mass_flow_kgps=5.0, dt=2.0)
        self.assertAlmostEqual(dry.mass_kg, 6.0)
        self.assertAlmostEqual(dry.fuel_remaining_kg, 0.0)
        self.assertTrue(np.allclose(dry.inertia_kgm2, np.diag([2.0, 3.0, 4.0])))

        with self.assertRaises(ValueError):
            FuelMassInertiaModel(5.0, 6.0, np.eye(3), np.eye(3))
        with self.assertRaises(ValueError):
            model.step(10.0, -1.0, 0.1)

    def test_actuator_command_shaper_handles_delay_rate_deadband_and_backlash(self):
        delayed = ActuatorCommandShaper(limit=(-0.5, 0.5), rate_limit_per_s=1.0, delay_s=0.1)
        first = delayed.step(0.4, dt=0.0, t=0.0)
        second = delayed.step(0.4, dt=0.05, t=0.05)
        third = delayed.step(0.4, dt=0.06, t=0.11)

        self.assertAlmostEqual(first.output, 0.0)
        self.assertAlmostEqual(second.output, 0.0)
        self.assertAlmostEqual(third.delayed_command, 0.4)
        self.assertAlmostEqual(third.output, 0.06)
        self.assertTrue(third.rate_limited)

        deadband = ActuatorCommandShaper(deadband=0.05)
        self.assertAlmostEqual(deadband.step(0.03, dt=0.1).output, 0.0)

        backlash = ActuatorCommandShaper(backlash=0.1)
        held = backlash.step(0.05, dt=0.1)
        moved = backlash.step(0.2, dt=0.1)
        self.assertAlmostEqual(held.output, 0.0)
        self.assertTrue(held.in_backlash)
        self.assertAlmostEqual(moved.output, 0.1)

        with self.assertRaises(ValueError):
            delayed.step(0.0, dt=0.1, t=0.01)

    def test_latency_buffer_interpolates_and_rejects_out_of_order_samples(self):
        buffer = LatencyBuffer(latency_s=0.5)
        buffer.add(0.0, [0.0, 0.0, 0.0])
        buffer.add(1.0, [10.0, 0.0, 0.0])
        delayed = buffer.sample(1.0)

        self.assertTrue(np.allclose(delayed, [5.0, 0.0, 0.0]))
        with self.assertRaises(ValueError):
            buffer.add(0.5, [5.0, 0.0, 0.0])

    def test_sensor_latency_bias_drift_is_deterministic_without_rng_and_bounded_with_rng(self):
        sensor = SensorLatencyBias(
            latency_s=0.2,
            initial_bias=np.array([1.0, 0.0, 0.0]),
            drift_rate_per_s=np.array([0.1, 0.0, 0.0]),
            random_walk_std_per_sqrt_s=np.array([0.01, 0.01, 0.01]),
            bias_limit=np.array([1.05, 0.02, 0.02]),
        )
        first = sensor.sample(0.0, [0.0, 0.0, 0.0], dt=0.0)
        second = sensor.sample(0.4, [4.0, 0.0, 0.0], dt=0.4)

        self.assertTrue(np.allclose(first.value, [1.0, 0.0, 0.0]))
        self.assertTrue(np.allclose(second.delayed_value, [2.0, 0.0, 0.0]))
        self.assertTrue(np.allclose(second.bias, [1.04, 0.0, 0.0]))
        self.assertTrue(np.allclose(second.value, [3.04, 0.0, 0.0]))

        rng = np.random.default_rng(4)
        noisy = sensor.sample(0.8, [8.0, 0.0, 0.0], dt=10.0, rng=rng)
        self.assertTrue(np.all(np.abs(noisy.bias) <= np.array([1.05, 0.02, 0.02]) + 1e-12))

        scalar = SensorLatencyBias(initial_bias=1.0)
        expanded = scalar.sample(0.0, [2.0, 3.0, 4.0], dt=0.0)
        self.assertEqual(expanded.value.shape, (3,))

        with self.assertRaises(ValueError):
            SensorLatencyBias(initial_bias=[0.0, math.nan, 0.0])


if __name__ == "__main__":
    unittest.main()
