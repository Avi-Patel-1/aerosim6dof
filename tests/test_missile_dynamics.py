import unittest

import numpy as np

from aerosim6dof.scenario import Scenario
from aerosim6dof.simulation.missile_dynamics import (
    ActuatorConfig,
    FuzeConfig,
    GuidanceConfig,
    MissileDynamicsConfig,
    MissileState,
    MotorConfig,
    SeekerConfig,
    TargetState,
    evaluate_fuze,
    measure_seeker,
    proportional_navigation,
    rate_limit_vector,
    sample_motor,
    step_missile,
)


class MissileDynamicsTests(unittest.TestCase):
    def test_seeker_gates_by_range_and_field_of_view(self):
        cfg = SeekerConfig(min_range_m=10.0, max_range_m=1000.0, field_of_view_deg=60.0)
        valid = measure_seeker(
            np.array([0.0, 0.0, 0.0]),
            np.array([100.0, 0.0, 0.0]),
            np.array([500.0, 50.0, 0.0]),
            np.array([0.0, 0.0, 0.0]),
            cfg,
        )
        self.assertTrue(valid.valid)
        self.assertEqual(valid.status, "valid")
        self.assertGreater(valid.closing_speed_mps, 0.0)
        self.assertTrue(np.all(np.isfinite(valid.line_of_sight_rate_rps)))

        too_far = measure_seeker(
            np.zeros(3),
            np.array([100.0, 0.0, 0.0]),
            np.array([1100.0, 0.0, 0.0]),
            np.zeros(3),
            cfg,
        )
        self.assertFalse(too_far.valid)
        self.assertEqual(too_far.status, "range_above_max")

        out_of_fov = measure_seeker(
            np.zeros(3),
            np.array([100.0, 0.0, 0.0]),
            np.array([500.0, 500.0, 0.0]),
            np.zeros(3),
            cfg,
        )
        self.assertFalse(out_of_fov.valid)
        self.assertEqual(out_of_fov.status, "outside_fov")

    def test_proportional_navigation_commands_lateral_acceleration_and_limits(self):
        measurement = measure_seeker(
            np.zeros(3),
            np.array([300.0, 0.0, 0.0]),
            np.array([1000.0, 0.0, 100.0]),
            np.zeros(3),
            SeekerConfig(field_of_view_deg=180.0),
        )
        command = proportional_navigation(
            measurement,
            GuidanceConfig(navigation_constant=3.0, max_accel_mps2=25.0),
        )
        self.assertTrue(command.valid)
        self.assertTrue(command.saturated)
        self.assertAlmostEqual(np.linalg.norm(command.acceleration_command_mps2), 25.0)
        self.assertGreater(command.acceleration_command_mps2[2], 0.0)

        invalid = proportional_navigation(
            measure_seeker(
                np.zeros(3),
                np.array([1.0, 0.0, 0.0]),
                np.array([-10.0, 0.0, 0.0]),
                np.zeros(3),
                SeekerConfig(field_of_view_deg=10.0),
            ),
            GuidanceConfig(),
        )
        self.assertFalse(invalid.valid)
        self.assertEqual(invalid.status, "invalid_measurement")

    def test_motor_spools_samples_profile_and_burns_out(self):
        cfg = MotorConfig(
            max_thrust_n=1000.0,
            burn_time_s=2.0,
            spool_time_s=1.0,
            isp_s=200.0,
            thrust_profile=((0.0, 0.5), (1.0, 1.0)),
        )
        start = sample_motor(0.0, 0.1, cfg, mass_kg=10.0, dry_mass_kg=5.0)
        mid = sample_motor(0.5, 0.1, cfg, mass_kg=10.0, dry_mass_kg=5.0)
        full = sample_motor(1.5, 0.1, cfg, mass_kg=10.0, dry_mass_kg=5.0)
        burnout = sample_motor(2.1, 0.1, cfg, mass_kg=10.0, dry_mass_kg=5.0)
        self.assertEqual(start.thrust_n, 0.0)
        self.assertAlmostEqual(mid.spool_fraction, 0.5)
        self.assertGreater(mid.thrust_n, 0.0)
        self.assertAlmostEqual(full.thrust_n, 1000.0)
        self.assertGreater(full.mass_flow_kgps, 0.0)
        self.assertTrue(burnout.burned_out)
        self.assertEqual(burnout.thrust_n, 0.0)

    def test_actuator_vector_rate_limit_and_saturation(self):
        sample = rate_limit_vector(
            np.array([100.0, 0.0, 0.0]),
            np.zeros(3),
            0.1,
            ActuatorConfig(max_accel_mps2=50.0, rate_limit_mps3=20.0),
        )
        self.assertTrue(sample.saturated)
        self.assertTrue(sample.rate_limited)
        self.assertAlmostEqual(np.linalg.norm(sample.acceleration_mps2), 2.0)

    def test_fuze_requires_arming_then_proximity_triggers(self):
        measurement = measure_seeker(
            np.zeros(3),
            np.array([100.0, 0.0, 0.0]),
            np.array([5.0, 0.0, 0.0]),
            np.zeros(3),
            SeekerConfig(max_range_m=100.0),
        )
        cfg = FuzeConfig(arming_time_s=0.5, proximity_radius_m=10.0)
        safe = evaluate_fuze(0.1, measurement, config=cfg)
        armed = evaluate_fuze(0.6, measurement, config=cfg)
        self.assertFalse(safe.fuzed)
        self.assertEqual(safe.status, "safe")
        self.assertTrue(armed.fuzed)
        self.assertEqual(armed.status, "proximity")

    def test_step_missile_returns_state_and_flat_telemetry(self):
        cfg = MissileDynamicsConfig(
            dry_mass_kg=40.0,
            seeker=SeekerConfig(max_range_m=5000.0, field_of_view_deg=160.0),
            guidance=GuidanceConfig(navigation_constant=3.0, max_accel_mps2=80.0),
            motor=MotorConfig(max_thrust_n=1200.0, burn_time_s=2.0, spool_time_s=0.0, isp_s=200.0),
            actuator=ActuatorConfig(max_accel_mps2=80.0, rate_limit_mps3=800.0),
            fuze=FuzeConfig(arming_time_s=0.0, proximity_radius_m=5.0, self_destruct_time_s=20.0),
        )
        state = MissileState(
            time_s=0.0,
            position_m=np.array([0.0, 0.0, 0.0]),
            velocity_mps=np.array([250.0, 0.0, 0.0]),
            mass_kg=50.0,
        )
        target = TargetState(
            position_m=np.array([1000.0, 0.0, 100.0]),
            velocity_mps=np.zeros(3),
            target_id="demo_target",
        )
        result = step_missile(state, target, 0.05, cfg)
        self.assertGreater(result.state.position_m[0], state.position_m[0])
        self.assertLess(result.state.mass_kg, state.mass_kg)
        self.assertIn("seeker_range_m", result.telemetry)
        self.assertEqual(result.telemetry["target_id"], "demo_target")
        self.assertEqual(result.telemetry["seeker_valid"], 1.0)
        self.assertGreaterEqual(result.telemetry["motor_thrust_n"], 0.0)

    def test_config_from_dict_matches_optional_scenario_block(self):
        scenario = Scenario.from_file("examples/scenarios/missile_intercept_demo.json")
        self.assertIn("missile", scenario.raw)
        config = MissileDynamicsConfig.from_dict(scenario.raw["missile"])
        self.assertGreater(config.motor.max_thrust_n, 0.0)
        self.assertGreater(config.seeker.max_range_m, 1000.0)
        self.assertGreater(config.fuze.proximity_radius_m, 0.0)


if __name__ == "__main__":
    unittest.main()
