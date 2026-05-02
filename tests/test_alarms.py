import unittest

from aerosim6dof.analysis.alarms import evaluate_alarms


class AlarmEvaluationTests(unittest.TestCase):
    def test_qbar_alarm_tracks_cleared_lifecycle(self):
        alarms = evaluate_alarms(
            history=[
                {"time_s": 0.0, "qbar_pa": 12000.0},
                {"time_s": 1.0, "qbar_pa": 65000.0},
                {"time_s": 2.0, "qbar_pa": 58000.0},
            ]
        )
        alarm = next(item for item in alarms if item["id"] == "QBAR_HIGH")
        self.assertEqual(alarm["severity"], "warning")
        self.assertEqual(alarm["first_triggered_time_s"], 1.0)
        self.assertEqual(alarm["last_triggered_time_s"], 1.0)
        self.assertEqual(alarm["cleared_time_s"], 2.0)
        self.assertFalse(alarm["active"])
        self.assertEqual(alarm["occurrence_count"], 1)

    def test_sensor_and_actuator_rules_use_non_history_files(self):
        alarms = evaluate_alarms(
            controls=[
                {"time_s": 0.0, "elevator_saturated": 0.0, "aileron_saturated": 0.0, "rudder_saturated": 0.0},
                {"time_s": 0.5, "elevator_saturated": 1.0, "aileron_saturated": 0.0, "rudder_saturated": 0.0},
            ],
            sensors=[
                {"time_s": 0.0, "gps_valid": 1.0},
                {"time_s": 0.5, "gps_valid": 0.0},
            ],
        )
        ids = {alarm["id"] for alarm in alarms}
        self.assertIn("GPS_DROPOUT", ids)
        self.assertIn("ACTUATOR_SATURATION", ids)

    def test_thrust_loss_stays_active_when_throttle_is_commanded(self):
        alarms = evaluate_alarms(
            history=[
                {"time_s": 0.0, "thrust_n": 100.0, "throttle": 0.8},
                {"time_s": 1.0, "thrust_n": 0.0, "throttle": 0.8},
            ]
        )
        alarm = next(item for item in alarms if item["id"] == "ENGINE_THRUST_LOSS")
        self.assertEqual(alarm["severity"], "critical")
        self.assertTrue(alarm["active"])
        self.assertIsNone(alarm["cleared_time_s"])

    def test_low_altitude_alarm_prefers_agl_when_available(self):
        alarms = evaluate_alarms(
            history=[
                {"time_s": 0.0, "altitude_m": 500.0, "altitude_agl_m": 160.0, "vz_mps": -10.0},
                {"time_s": 1.0, "altitude_m": 450.0, "altitude_agl_m": 80.0, "vz_mps": -25.0},
            ]
        )
        alarm = next(item for item in alarms if item["id"] == "LOW_ALTITUDE_HIGH_DESCENT_RATE")
        self.assertEqual(alarm["severity"], "critical")
        self.assertEqual(alarm["first_triggered_time_s"], 1.0)

    def test_missing_or_nonnumeric_channels_do_not_crash(self):
        alarms = evaluate_alarms(
            history=[
                {"time_s": 0.0, "qbar_pa": "not numeric"},
                {"time_s": 1.0, "altitude_m": 80.0, "vz_mps": "down"},
            ],
            controls=[{"time_s": 0.0, "elevator_saturated": 1.0}],
            sensors=[{"time_s": 0.0, "gps_valid": "unknown"}],
        )
        self.assertEqual(alarms, [])

    def test_target_miss_distance_alarm_uses_summary(self):
        alarms = evaluate_alarms(summary={"min_target_distance_m": 250.0, "final": {"time_s": 12.0}})
        alarm = next(item for item in alarms if item["id"] == "TARGET_MISS_DISTANCE_HIGH")
        self.assertEqual(alarm["subsystem"], "GNC")
        self.assertEqual(alarm["first_triggered_time_s"], 12.0)
        self.assertTrue(alarm["active"])


if __name__ == "__main__":
    unittest.main()
