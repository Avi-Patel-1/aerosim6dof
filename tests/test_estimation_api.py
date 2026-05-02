import json
from pathlib import Path
import tempfile
import unittest

from aerosim6dof.estimation.navigation_filter import load_navigation_telemetry_from_run
from aerosim6dof.reports.csv_writer import write_csv


class EstimationApiPayloadTests(unittest.TestCase):
    def test_run_loader_returns_json_serializable_flat_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_csv(
                run_dir / "sensors.csv",
                [
                    {
                        "time_s": 0.0,
                        "sensor_time_s": 0.0,
                        "gps_valid": 1.0,
                        "gps_x_m": 1.0,
                        "gps_y_m": 2.0,
                        "gps_z_m": 30.0,
                        "extra_nested_like_name": "ignored",
                    }
                ],
            )
            write_csv(
                run_dir / "truth.csv",
                [
                    {
                        "time_s": 0.0,
                        "x_m": 1.0,
                        "y_m": 2.0,
                        "altitude_m": 30.0,
                        "vx_mps": 0.0,
                        "vy_mps": 0.0,
                        "vz_mps": 0.0,
                    }
                ],
            )

            payload = load_navigation_telemetry_from_run(run_dir)

        json.dumps(payload)
        self.assertEqual(set(payload), {"rows", "channels", "summary"})
        self.assertEqual(payload["summary"]["row_count"], 1)
        row = payload["rows"][0]
        for key, value in row.items():
            self.assertFalse(isinstance(value, (dict, list, tuple)), key)
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
            self.assertIn(key, row)

    def test_missing_run_csvs_return_empty_payload_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = load_navigation_telemetry_from_run(tmp)

        self.assertEqual(payload["rows"], [])
        self.assertGreaterEqual(len(payload["channels"]), 1)
        self.assertEqual(payload["summary"]["row_count"], 0)
        self.assertIn("no navigation source rows found in sensors.csv or history.csv", payload["summary"]["warnings"])


if __name__ == "__main__":
    unittest.main()
