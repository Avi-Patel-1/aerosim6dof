import unittest
from types import SimpleNamespace

import numpy as np

from aerosim6dof.simulation.interceptors import InterceptorSuite


def _target_row(x_m: float, y_m: float = 0.0, z_m: float = 0.0, vx_mps: float = 0.0) -> dict[str, float | str]:
    return {
        "time_s": 0.0,
        "target_id": "target",
        "target_role": "primary",
        "target_active": 1.0,
        "target_x_m": x_m,
        "target_y_m": y_m,
        "target_z_m": z_m,
        "target_vx_mps": vx_mps,
        "target_vy_mps": 0.0,
        "target_vz_mps": 0.0,
    }


def _missile_config() -> dict[str, object]:
    return {
        "dry_mass_kg": 40.0,
        "initial_mass_kg": 50.0,
        "seeker": {"max_range_m": 5000.0, "field_of_view_deg": 180.0},
        "guidance": {
            "navigation_constant": 3.0,
            "max_accel_mps2": 80.0,
            "require_valid_measurement": True,
        },
        "motor": {"max_thrust_n": 1200.0, "burn_time_s": 2.0, "spool_time_s": 0.0, "isp_s": 220.0},
        "actuator": {"max_accel_mps2": 80.0, "rate_limit_mps3": 1000.0},
        "fuze": {"arming_time_s": 0.0, "proximity_radius_m": 6.0, "self_destruct_time_s": 20.0},
    }


class MissileRuntimeIntegrationTests(unittest.TestCase):
    def test_missile_mode_uses_step_missile_and_emits_runtime_columns(self):
        scenario = SimpleNamespace(
            raw={
                "missile": _missile_config(),
                "interceptors": [
                    {
                        "id": "missile-1",
                        "target_id": "target",
                        "launch_time_s": 0.0,
                        "initial_position_m": [0.0, 0.0, 0.0],
                        "initial_velocity_mps": [120.0, 0.0, 0.0],
                        "model": "missile",
                    }
                ],
            }
        )
        suite = InterceptorSuite.from_scenario(scenario)

        state, rows, events = suite.step(
            0.0,
            0.1,
            np.zeros(3),
            np.zeros(3),
            [_target_row(300.0, y_m=40.0)],
        )

        self.assertEqual(events[0]["type"], "interceptor_launch")
        self.assertEqual(rows[0]["missile_mode"], 1.0)
        self.assertEqual(rows[0]["seeker_valid"], 1.0)
        self.assertGreater(rows[0]["interceptor_x_m"], 0.0)
        self.assertGreater(rows[0]["missile_motor_thrust_n"], 0.0)
        self.assertGreater(rows[0]["missile_motor_mass_flow_kgps"], 0.0)
        self.assertGreater(rows[0]["missile_closing_speed_mps"], 0.0)
        self.assertIn("missile_lateral_accel_mps2", rows[0])
        self.assertGreater(rows[0]["missile_speed_mps"], 0.0)
        self.assertGreater(rows[0]["missile_mass_kg"], 0.0)
        self.assertGreater(rows[0]["missile_seeker_range_m"], 0.0)
        self.assertEqual(rows[0]["missile_seeker_status"], "valid")
        self.assertEqual(rows[0]["missile_guidance_valid"], 1.0)
        self.assertEqual(rows[0]["missile_motor_spool_fraction"], 1.0)
        self.assertEqual(rows[0]["missile_motor_phase"], "boost")
        self.assertIn("missile_fuze_status", rows[0])
        self.assertEqual(state["missile_mode"], 1.0)

    def test_missile_mode_closes_range_over_tiny_target_sequence(self):
        scenario = SimpleNamespace(
            raw={
                "missile": _missile_config(),
                "interceptors": [
                    {
                        "id": "missile-1",
                        "target_id": "target",
                        "launch_time_s": 0.0,
                        "initial_position_m": [0.0, 0.0, 0.0],
                        "initial_velocity_mps": [140.0, 0.0, 0.0],
                        "dynamics_model": "missile_dynamics_v1",
                        "proximity_fuze_m": 6.0,
                    }
                ],
            }
        )
        suite = InterceptorSuite.from_scenario(scenario)
        ranges: list[float] = []
        events: list[dict[str, object]] = []

        for step in range(12):
            target = _target_row(220.0 - 3.0 * step)
            _, rows, step_events = suite.step(
                step * 0.1,
                0.1,
                np.zeros(3),
                np.zeros(3),
                [target],
            )
            ranges.append(float(rows[0]["interceptor_range_m"]))
            events.extend(step_events)

        self.assertLess(min(ranges[1:]), ranges[0])
        self.assertTrue(any(row.missile_state is not None for row in suite.interceptors))
        self.assertTrue(ranges[-1] < ranges[0] or any(event.get("type") == "interceptor_fuze" for event in events))

    def test_interceptor_missile_block_overrides_top_level_config(self):
        top_level = _missile_config()
        top_level["motor"] = {"max_thrust_n": 0.0, "burn_time_s": 2.0, "spool_time_s": 0.0}
        scenario = SimpleNamespace(
            raw={
                "missile": top_level,
                "interceptors": [
                    {
                        "id": "missile-1",
                        "target_id": "target",
                        "launch_time_s": 0.0,
                        "initial_position_m": [0.0, 0.0, 0.0],
                        "initial_velocity_mps": [100.0, 0.0, 0.0],
                        "dynamics_model": "missile_dynamics_v1",
                        "missile": {
                            "initial_mass_kg": 52.0,
                            "motor": {"max_thrust_n": 900.0, "isp_s": 220.0},
                        },
                    }
                ],
            }
        )
        suite = InterceptorSuite.from_scenario(scenario)

        _, rows, _ = suite.step(0.0, 0.1, np.zeros(3), np.zeros(3), [_target_row(200.0)])

        self.assertAlmostEqual(rows[0]["missile_motor_thrust_n"], 900.0)

    def test_legacy_kinematic_mode_remains_default(self):
        scenario = SimpleNamespace(
            raw={
                "interceptors": [
                    {
                        "id": "legacy-1",
                        "target_id": "target",
                        "launch_time_s": 0.0,
                        "initial_position_m": [0.0, 0.0, 0.0],
                        "initial_velocity_mps": [0.0, 0.0, 0.0],
                        "max_speed_mps": 50.0,
                        "max_accel_mps2": 20.0,
                        "guidance_gain": 1.0,
                    }
                ]
            }
        )
        suite = InterceptorSuite.from_scenario(scenario)

        _, rows, events = suite.step(0.0, 0.1, np.zeros(3), np.zeros(3), [_target_row(100.0)])

        self.assertEqual(events[0]["type"], "interceptor_launch")
        self.assertNotIn("missile_mode", rows[0])
        self.assertGreater(rows[0]["interceptor_x_m"], 0.0)
        self.assertLess(rows[0]["interceptor_range_m"], 100.0)


if __name__ == "__main__":
    unittest.main()
