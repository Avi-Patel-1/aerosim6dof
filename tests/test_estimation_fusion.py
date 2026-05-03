import json
import math
from pathlib import Path
import tempfile
import unittest

from aerosim6dof.analysis.estimation_report import estimation_report
from aerosim6dof.estimation.fusion import align_run_tables, build_estimation_fusion
from aerosim6dof.reports.csv_writer import read_csv, write_csv


class EstimationFusionReportTests(unittest.TestCase):
    def test_report_aligns_run_csvs_and_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_csv(run_dir / "truth.csv", _truth_rows())
            write_csv(run_dir / "sensors.csv", _sensor_rows())
            write_csv(run_dir / "history.csv", _history_rows())

            summary = estimation_report(run_dir, run_dir / "estimation", max_time_gap_s=0.2)

            self.assertEqual(summary["row_count"], 3)
            self.assertEqual(summary["source_files"], ["truth.csv", "sensors.csv", "history.csv"])
            self.assertAlmostEqual(summary["quality"]["gnss"]["valid_fraction"], 2.0 / 3.0)
            self.assertEqual(summary["quality"]["gnss"]["dropout_events"], 2)
            for comparison in ("gnss_position", "barometer", "pitot", "radar_altimeter", "imu_gyro"):
                self.assertIn(comparison, summary["available_comparisons"])

            artifacts = summary["artifacts"]
            for key in ("summary_json", "metrics_csv", "residuals_csv", "report_html"):
                self.assertTrue(Path(artifacts[key]).exists(), key)
            self.assertGreaterEqual(len(artifacts["plots"]), 4)
            for plot in artifacts["plots"]:
                self.assertTrue(Path(plot).exists(), plot)

            residuals = read_csv(run_dir / "estimation" / "residuals.csv")
            self.assertEqual(len(residuals), 3)
            self.assertAlmostEqual(residuals[0]["sensor_time_delta_s"], 0.02)
            self.assertAlmostEqual(residuals[0]["baro_altitude_residual_m"], 3.0)
            self.assertAlmostEqual(residuals[0]["pitot_airspeed_residual_mps"], 1.0)
            self.assertAlmostEqual(residuals[0]["radar_altitude_residual_m"], -2.0)
            self.assertAlmostEqual(residuals[0]["gyro_p_residual_rps"], 0.1, places=6)
            self.assertEqual(residuals[1]["gnss_available"], 0.0)

            metrics = {row["metric"]: row for row in read_csv(run_dir / "estimation" / "estimation_metrics.csv")}
            self.assertEqual(metrics["baro_altitude_residual_m"]["samples"], 3.0)
            self.assertEqual(metrics["gnss_position_error_m"]["samples"], 2.0)
            self.assertIn("current", metrics["estimate_position_error_m"])
            self.assertIn("rmse", metrics["pitot_airspeed_residual_mps"])

            with Path(artifacts["summary_json"]).open() as f:
                persisted = json.load(f)
            self.assertEqual(persisted["row_count"], summary["row_count"])

    def test_history_only_run_is_defensive_on_missing_sensor_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_csv(
                run_dir / "history.csv",
                [
                    {"time_s": 0.0, "x_m": 0.0, "y_m": 0.0, "altitude_m": 50.0, "baro_alt_m": 51.0, "baro_valid": 1.0},
                    {"time_s": 1.0, "x_m": 1.0, "y_m": 0.0, "altitude_m": 51.0, "baro_alt_m": 52.5, "baro_valid": 1.0},
                ],
            )

            summary = estimation_report(run_dir)

            self.assertEqual(summary["row_count"], 2)
            self.assertEqual(summary["source_files"], ["history.csv"])
            self.assertFalse(summary["quality"]["gnss"]["present"])
            self.assertIn("barometer", summary["available_comparisons"])
            self.assertIn("GNSS channels unavailable; GNSS residual metrics were omitted", summary["warnings"])
            self.assertTrue((run_dir / "estimation_fusion" / "estimation_report.html").exists())
            residuals = read_csv(run_dir / "estimation_fusion" / "residuals.csv")
            self.assertAlmostEqual(residuals[-1]["baro_altitude_residual_m"], 1.5)

    def test_build_estimation_fusion_ignores_bad_optional_columns(self):
        result = build_estimation_fusion(
            truth_rows=[
                {
                    "time_s": 0.0,
                    "x_m": 0.0,
                    "y_m": 0.0,
                    "altitude_m": 10.0,
                    "vx_mps": 1.0,
                    "vy_mps": 0.0,
                    "vz_mps": 0.0,
                    "airspeed_mps": 5.0,
                }
            ],
            sensor_rows=[
                {
                    "time_s": 0.0,
                    "gps_valid": "not numeric",
                    "gps_x_m": "bad",
                    "baro_alt_m": "also bad",
                    "pitot_valid": 1.0,
                    "pitot_airspeed_mps": 6.0,
                    "future_sensor_payload": "ignored",
                }
            ],
        )

        self.assertEqual(result["summary"]["row_count"], 1)
        row = result["residuals"][0]
        self.assertNotIn("gnss_position_error_m", row)
        self.assertAlmostEqual(row["pitot_airspeed_residual_mps"], 1.0)
        metric_names = {metric["metric"] for metric in result["metric_rows"]}
        self.assertIn("pitot_airspeed_residual_mps", metric_names)

    def test_alignment_uses_nearest_rows_on_truth_time_base(self):
        samples = align_run_tables(
            truth_rows=[{"time_s": 0.0}, {"time_s": 1.0}],
            sensor_rows=[{"time_s": 0.1, "gps_valid": 1.0}, {"time_s": 1.1, "gps_valid": 1.0}],
            history_rows=[{"time_s": 0.0}, {"time_s": 1.0}],
            max_time_gap_s=0.2,
        )

        self.assertEqual([sample.time_s for sample in samples], [0.0, 1.0])
        self.assertAlmostEqual(samples[0].sensor_time_delta_s, 0.1)
        self.assertAlmostEqual(samples[1].sensor_time_delta_s, 0.1)
        self.assertEqual(samples[0].sensors["gps_valid"], 1.0)

    def test_radar_altimeter_uses_terrain_relative_truth_when_available(self):
        result = build_estimation_fusion(
            truth_rows=[{"time_s": 0.0, "x_m": 0.0, "y_m": 0.0, "altitude_m": 120.0, "terrain_elevation_m": 100.0}],
            sensor_rows=[{"time_s": 0.0, "radar_valid": 1.0, "radar_agl_m": 19.0}],
            history_rows=[{"time_s": 0.0, "terrain_elevation_m": 100.0}],
        )

        row = result["residuals"][0]
        self.assertAlmostEqual(row["truth_agl_m"], 20.0)
        self.assertAlmostEqual(row["radar_altitude_residual_m"], -1.0)
        self.assertAlmostEqual(row["estimate_z_m"], 119.0)


def _truth_rows():
    return [
        {
            "time_s": 0.0,
            "x_m": 0.0,
            "y_m": 0.0,
            "altitude_m": 100.0,
            "vx_mps": 10.0,
            "vy_mps": 0.0,
            "vz_mps": 1.0,
            "speed_mps": math.sqrt(101.0),
            "airspeed_mps": 10.0,
            "p_dps": math.degrees(1.0),
            "q_dps": 0.0,
            "r_dps": 0.0,
        },
        {
            "time_s": 1.0,
            "x_m": 10.0,
            "y_m": 0.0,
            "altitude_m": 110.0,
            "vx_mps": 10.0,
            "vy_mps": 0.0,
            "vz_mps": 1.0,
            "speed_mps": math.sqrt(101.0),
            "airspeed_mps": 11.0,
            "p_dps": math.degrees(1.0),
            "q_dps": 0.0,
            "r_dps": 0.0,
        },
        {
            "time_s": 2.0,
            "x_m": 20.0,
            "y_m": 0.0,
            "altitude_m": 120.0,
            "vx_mps": 10.0,
            "vy_mps": 0.0,
            "vz_mps": 1.0,
            "speed_mps": math.sqrt(101.0),
            "airspeed_mps": 12.0,
            "p_dps": math.degrees(1.0),
            "q_dps": 0.0,
            "r_dps": 0.0,
        },
    ]


def _sensor_rows():
    return [
        {
            "time_s": 0.02,
            "sensor_time_s": 0.02,
            "gps_valid": 1.0,
            "gps_x_m": 1.0,
            "gps_y_m": 0.0,
            "gps_z_m": 102.0,
            "gps_vx_mps": 9.5,
            "gps_vy_mps": 0.0,
            "gps_vz_mps": 1.1,
            "baro_valid": 1.0,
            "baro_alt_m": 103.0,
            "pitot_valid": 1.0,
            "pitot_airspeed_mps": 11.0,
            "radar_valid": 1.0,
            "radar_agl_m": 98.0,
            "imu_valid": 1.0,
            "gyro_p_rps": 1.1,
            "gyro_q_rps": 0.0,
            "gyro_r_rps": 0.0,
        },
        {
            "time_s": 1.02,
            "sensor_time_s": 1.02,
            "gps_valid": 0.0,
            "gps_x_m": 999.0,
            "gps_y_m": 999.0,
            "gps_z_m": 999.0,
            "baro_valid": 1.0,
            "baro_alt_m": 112.0,
            "pitot_valid": 1.0,
            "pitot_airspeed_mps": 12.0,
            "radar_valid": 1.0,
            "radar_agl_m": 109.0,
            "imu_valid": 1.0,
            "gyro_p_rps": 0.9,
            "gyro_q_rps": 0.0,
            "gyro_r_rps": 0.0,
        },
        {
            "time_s": 2.02,
            "sensor_time_s": 2.02,
            "gps_valid": 1.0,
            "gps_x_m": 21.0,
            "gps_y_m": 0.0,
            "gps_z_m": 121.0,
            "gps_vx_mps": 10.5,
            "gps_vy_mps": 0.0,
            "gps_vz_mps": 0.9,
            "baro_valid": 1.0,
            "baro_alt_m": 123.0,
            "pitot_valid": 1.0,
            "pitot_airspeed_mps": 13.0,
            "radar_valid": 1.0,
            "radar_agl_m": 119.0,
            "imu_valid": 1.0,
            "gyro_p_rps": 1.0,
            "gyro_q_rps": 0.0,
            "gyro_r_rps": 0.0,
        },
    ]


def _history_rows():
    return [
        {"time_s": 0.0, "x_m": 0.0, "y_m": 0.0, "altitude_m": 100.0},
        {"time_s": 1.0, "x_m": 10.0, "y_m": 0.0, "altitude_m": 110.0},
        {"time_s": 2.0, "x_m": 20.0, "y_m": 0.0, "altitude_m": 120.0},
    ]


if __name__ == "__main__":
    unittest.main()
