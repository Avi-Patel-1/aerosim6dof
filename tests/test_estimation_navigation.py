from pathlib import Path
import tempfile
import unittest

import numpy as np

from aerosim6dof.estimation import (
    ConstantVelocityNavigationFilter,
    build_navigation_telemetry,
    gnss_quality_score,
)
from aerosim6dof.estimation.navigation_filter import load_navigation_telemetry_from_run
from aerosim6dof.reports.csv_writer import write_csv


class EstimationNavigationTests(unittest.TestCase):
    def test_constant_velocity_filter_reduces_position_error_with_gnss(self):
        rows = []
        truth = []
        for index in range(10):
            t = float(index)
            true_x = 100.0 + 20.0 * t
            truth.append({"time_s": t, "x_m": true_x, "y_m": 0.0, "altitude_m": 50.0, "vx_mps": 20.0, "vy_mps": 0.0, "vz_mps": 0.0})
            rows.append(
                {
                    "sensor_time_s": t,
                    "gps_valid": 1.0,
                    "gps_x_m": true_x + 10.0 / (index + 1),
                    "gps_y_m": 0.5,
                    "gps_z_m": 51.0,
                    "gps_vx_mps": 20.0,
                    "gps_vy_mps": 0.0,
                    "gps_vz_mps": 0.0,
                    "gps_position_noise_std_m": 2.0,
                    "gps_velocity_noise_std_mps": 0.2,
                }
            )

        telemetry = build_navigation_telemetry(
            rows,
            truth,
            config={"process_noise_accel_mps2": 0.2, "gnss_position_noise_m": 2.0, "gnss_velocity_noise_mps": 0.2},
        )

        self.assertEqual(len(telemetry), 10)
        self.assertGreater(telemetry[0]["position_error_m"], telemetry[-1]["position_error_m"])
        self.assertGreater(telemetry[0]["covariance_trace"], telemetry[-1]["covariance_trace"])
        self.assertEqual(telemetry[-1]["gnss_used"], 1.0)
        self.assertEqual(telemetry[-1]["update_dimension"], 6.0)
        self.assertLess(telemetry[-1]["position_error_m"], 3.0)

    def test_dropout_predicts_without_update_and_keeps_covariance_finite(self):
        filt = ConstantVelocityNavigationFilter(process_noise_accel_mps2=0.1, gnss_position_noise_m=1.0)
        filt.initialize(position_m=(0.0, 0.0, 0.0), velocity_mps=(10.0, 0.0, 1.0), time_s=0.0)

        estimate = filt.step(
            {
                "sensor_time_s": 1.0,
                "gps_valid": 0.0,
                "gps_x_m": 1000.0,
                "gps_y_m": 1000.0,
                "gps_z_m": 1000.0,
            }
        )

        self.assertFalse(estimate.gnss_used)
        self.assertAlmostEqual(float(estimate.position_m[0]), 10.0, places=6)
        self.assertAlmostEqual(float(estimate.position_m[2]), 1.0, places=6)
        self.assertTrue(np.all(np.isfinite(estimate.covariance)))
        self.assertGreaterEqual(float(np.min(np.diag(estimate.covariance))), 0.0)

    def test_gnss_quality_penalizes_dropout_noise_and_latency(self):
        good = gnss_quality_score(
            {
                "gps_valid": 1.0,
                "gps_x_m": 1.0,
                "gps_y_m": 2.0,
                "gps_z_m": 3.0,
                "gps_position_noise_std_m": 0.5,
                "gps_velocity_noise_std_mps": 0.1,
                "gps_dropout_probability": 0.0,
                "gps_latency_s": 0.0,
            }
        )
        degraded = gnss_quality_score(
            {
                "gps_valid": 1.0,
                "gps_x_m": 1.0,
                "gps_y_m": 2.0,
                "gps_z_m": 3.0,
                "gps_position_noise_std_m": 40.0,
                "gps_velocity_noise_std_mps": 8.0,
                "gps_dropout_probability": 0.4,
                "gps_latency_s": 2.0,
            }
        )

        self.assertGreater(good, degraded)
        self.assertGreater(good, 0.7)
        self.assertGreater(degraded, 0.0)
        self.assertEqual(gnss_quality_score({"gps_valid": 0.0, "gps_x_m": 1.0}), 0.0)
        self.assertEqual(gnss_quality_score({"gps_valid": "not numeric", "gps_x_m": 1.0, "gps_y_m": 2.0, "gps_z_m": 3.0}), 0.0)
        self.assertEqual(gnss_quality_score({"gps_valid": 1.0, "gps_dropout_active": 1.0, "gps_x_m": 1.0}), 0.0)
        self.assertLess(
            gnss_quality_score({"gps_valid": 1.0, "gps_x_m": 1.0, "gps_y_m": 2.0, "gps_z_m": 3.0}, config={"gps": {"dropout_probability": 0.5}}),
            0.6,
        )

    def test_non_numeric_and_missing_sensor_values_do_not_crash(self):
        rows = [
            {
                "time_s": 0.0,
                "x_m": 0.0,
                "y_m": 0.0,
                "altitude_m": 10.0,
                "vx_mps": 1.0,
                "vy_mps": 0.0,
                "vz_mps": 0.0,
                "gps_valid": "yes",
                "gps_x_m": "bad",
                "gps_y_m": None,
                "gps_z_m": "nan",
            },
            {
                "time_s": 1.0,
                "x_m": 1.0,
                "y_m": 0.0,
                "altitude_m": 10.0,
                "vx_mps": 1.0,
                "vy_mps": 0.0,
                "vz_mps": 0.0,
                "gps_valid": 1.0,
                "gps_x_m": 1.2,
                "gps_y_m": 0.1,
                "gps_z_m": 9.8,
                "gps_vx_mps": "not numeric",
            },
        ]

        telemetry = build_navigation_telemetry(rows)

        self.assertEqual(len(telemetry), 2)
        self.assertEqual(telemetry[0]["gnss_used"], 0.0)
        self.assertEqual(telemetry[1]["gnss_used"], 1.0)
        self.assertEqual(telemetry[1]["update_dimension"], 3.0)
        for row in telemetry:
            self.assertTrue(np.isfinite(row["estimate_x_m"]))
            self.assertTrue(np.isfinite(row["covariance_trace"]))
            self.assertIn("position_error_m", row)

    def test_invalid_first_gnss_row_does_not_seed_state_from_stale_values(self):
        telemetry = build_navigation_telemetry(
            [
                {
                    "time_s": 0.0,
                    "x_m": 0.0,
                    "y_m": 0.0,
                    "altitude_m": 0.0,
                    "gps_valid": 0.0,
                    "gps_x_m": 999.0,
                    "gps_y_m": 999.0,
                    "gps_z_m": 999.0,
                },
                {
                    "time_s": 1.0,
                    "x_m": 1.0,
                    "y_m": 0.0,
                    "altitude_m": 0.0,
                    "gps_valid": 1.0,
                    "gps_x_m": 1.0,
                    "gps_y_m": 0.0,
                    "gps_z_m": 0.0,
                },
            ]
        )

        self.assertEqual(telemetry[0]["gnss_used"], 0.0)
        self.assertLess(abs(telemetry[0]["estimate_x_m"]), 1.0)
        self.assertLess(telemetry[1]["position_error_m"], 0.1)

    def test_truth_rows_are_optional_and_history_rows_are_supported(self):
        rows = [
            {
                "time_s": 0.0,
                "x_m": 5.0,
                "y_m": -2.0,
                "altitude_m": 100.0,
                "vx_mps": 3.0,
                "vy_mps": 0.0,
                "vz_mps": -1.0,
                "gps_valid": 1.0,
                "gps_x_m": 5.5,
                "gps_y_m": -2.0,
                "gps_z_m": 99.5,
                "gps_vx_mps": 3.0,
                "gps_vy_mps": 0.0,
                "gps_vz_mps": -1.0,
            }
        ]

        telemetry = build_navigation_telemetry(rows)

        self.assertAlmostEqual(telemetry[0]["truth_z_m"], 100.0)
        self.assertIn("sensor_gps_z_m", telemetry[0])
        self.assertIn("gps_position_error_m", telemetry[0])
        self.assertIn("velocity_error_mps", telemetry[0])

    def test_build_navigation_telemetry_emits_api_ready_aliases(self):
        telemetry = build_navigation_telemetry(
            [
                {
                    "time_s": 0.0,
                    "x_m": 0.0,
                    "y_m": 0.0,
                    "altitude_m": 10.0,
                    "vx_mps": 3.0,
                    "vy_mps": 4.0,
                    "vz_mps": 0.0,
                    "gps_valid": 1.0,
                    "gps_x_m": 0.0,
                    "gps_y_m": 0.0,
                    "gps_z_m": 10.0,
                    "gps_vx_mps": 3.0,
                    "gps_vy_mps": 4.0,
                    "gps_vz_mps": 0.0,
                    "unknown_future_sensor": "ignored",
                }
            ]
        )

        row = telemetry[0]
        self.assertEqual(row["estimate_altitude_m"], row["estimate_z_m"])
        self.assertAlmostEqual(row["estimate_speed_mps"], 5.0)
        self.assertEqual(row["estimate_position_error_m"], row["position_error_m"])
        self.assertEqual(row["estimate_velocity_error_mps"], row["velocity_error_mps"])
        self.assertEqual(row["gnss_quality"], row["gnss_quality_score"])
        self.assertEqual(row["gps_valid"], 1.0)

    def test_load_navigation_telemetry_from_run_uses_sensors_truth_and_stride(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_csv(
                run_dir / "sensors.csv",
                [
                    {"time_s": 0.0, "sensor_time_s": 0.0, "gps_valid": 1.0, "gps_x_m": 0.0, "gps_y_m": 0.0, "gps_z_m": 10.0},
                    {"time_s": 1.0, "sensor_time_s": 1.0, "gps_valid": 1.0, "gps_x_m": 1.0, "gps_y_m": 0.0, "gps_z_m": 10.5},
                    {
                        "time_s": 2.0,
                        "sensor_time_s": 2.0,
                        "gps_valid": 1.0,
                        "gps_x_m": 2.0,
                        "gps_y_m": 0.0,
                        "gps_z_m": 11.0,
                        "unexpected_sensor_column": 123.0,
                    },
                ],
            )
            write_csv(
                run_dir / "truth.csv",
                [
                    {"time_s": 0.0, "x_m": 0.0, "y_m": 0.0, "altitude_m": 10.0, "vx_mps": 1.0, "vy_mps": 0.0, "vz_mps": 0.5},
                    {"time_s": 1.0, "x_m": 1.0, "y_m": 0.0, "altitude_m": 10.5, "vx_mps": 1.0, "vy_mps": 0.0, "vz_mps": 0.5},
                    {"time_s": 2.0, "x_m": 2.0, "y_m": 0.0, "altitude_m": 11.0, "vx_mps": 1.0, "vy_mps": 0.0, "vz_mps": 0.5},
                ],
            )

            payload = load_navigation_telemetry_from_run(run_dir, stride=2)

        self.assertEqual(payload["summary"]["source"], "sensors_truth")
        self.assertEqual(payload["summary"]["input_row_count"], 3)
        self.assertEqual(payload["summary"]["row_count"], 2)
        self.assertEqual(payload["summary"]["stride"], 2)
        self.assertEqual(payload["summary"]["source_files"], ["sensors.csv", "truth.csv"])
        channel_keys = [channel["key"] for channel in payload["channels"]]
        for key in (
            "time_s",
            "estimate_x_m",
            "estimate_y_m",
            "estimate_z_m",
            "estimate_vx_mps",
            "estimate_vy_mps",
            "estimate_vz_mps",
            "estimate_altitude_m",
            "estimate_speed_mps",
            "estimate_position_error_m",
            "estimate_velocity_error_mps",
            "gnss_quality",
            "covariance_trace",
            "gps_valid",
        ):
            self.assertIn(key, payload["rows"][0])
            self.assertIn(key, channel_keys)

    def test_load_navigation_telemetry_from_run_falls_back_to_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_csv(
                run_dir / "history.csv",
                [
                    {
                        "time_s": 0.0,
                        "x_m": 5.0,
                        "y_m": 1.0,
                        "altitude_m": 50.0,
                        "vx_mps": 2.0,
                        "vy_mps": 0.0,
                        "vz_mps": 0.0,
                        "gps_x_m": 5.0,
                        "gps_y_m": 1.0,
                        "gps_z_m": 50.0,
                        "gps_valid": 1.0,
                    }
                ],
            )

            payload = load_navigation_telemetry_from_run(run_dir)

        self.assertEqual(payload["summary"]["source"], "history")
        self.assertEqual(payload["summary"]["source_files"], ["history.csv"])
        self.assertEqual(payload["summary"]["row_count"], 1)
        self.assertEqual(payload["rows"][0]["estimate_altitude_m"], payload["rows"][0]["estimate_z_m"])

    def test_packaged_nominal_web_run_smoke_when_available(self):
        run_dir = Path("outputs/web_runs/seed_scenario_suite/nominal_ascent")
        required = [run_dir / "sensors.csv", run_dir / "truth.csv", run_dir / "history.csv"]
        if not all(path.exists() for path in required):
            self.skipTest("packaged nominal web run is not available")

        payload = load_navigation_telemetry_from_run(run_dir, stride=200)

        self.assertGreater(payload["summary"]["row_count"], 0)
        self.assertEqual(payload["summary"]["source"], "sensors_truth")
        self.assertIsNotNone(payload["summary"]["max_estimate_position_error_m"])
        self.assertTrue(all(np.isfinite(row["covariance_trace"]) for row in payload["rows"]))


if __name__ == "__main__":
    unittest.main()
