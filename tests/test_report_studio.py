import tempfile
import unittest
from pathlib import Path

from aerosim6dof.reports.csv_writer import write_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.studio import REPORT_STUDIO_SCHEMA, assemble_report_studio_packet


class ReportStudioPacketTests(unittest.TestCase):
    def test_packet_assembles_summary_timeline_alarms_telemetry_engagement_and_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._write_sample_run(Path(tmp) / "mission_alpha")

            packet = assemble_report_studio_packet(run_dir, artifact_base_url="/api/artifacts/mission_alpha")

            self.assertEqual(packet["schema"], REPORT_STUDIO_SCHEMA)
            self.assertEqual(packet["packet_id"], "mission_alpha")
            self.assertEqual(packet["summary"]["data"]["scenario"], "Mission Alpha")

            highlight_keys = {item["key"] for item in packet["summary"]["highlights"]}
            self.assertIn("max_altitude_m", highlight_keys)
            self.assertIn("final.altitude_m", highlight_keys)

            timeline = packet["events_timeline"]
            self.assertEqual(timeline["count"], 3)
            self.assertEqual([item["time_s"] for item in timeline["items"]], [0.5, 1.4, 2.0])
            self.assertEqual(timeline["items"][1]["type"], "max_qbar")

            alarms = packet["alarm_summaries"]
            alarm_ids = {alarm["id"] for alarm in alarms["items"]}
            self.assertIn("QBAR_HIGH", alarm_ids)
            self.assertGreaterEqual(alarms["counts_by_severity"]["warning"], 1)

            telemetry = {item["id"]: item for item in packet["telemetry_highlights"]["items"]}
            self.assertEqual(telemetry["history.altitude_m"]["max"]["value"], 120.0)
            self.assertEqual(telemetry["history.qbar_pa"]["max"]["time_s"], 1.0)
            self.assertEqual(telemetry["controls.throttle"]["final"]["value"], 0.5)
            self.assertEqual(telemetry["sensors.gps_valid"]["min"]["value"], 0.0)

            engagement = packet["engagement_metrics"]
            self.assertEqual(engagement["target_ids"], ["target-a"])
            self.assertEqual(engagement["interceptor_ids"], ["int-1"])
            self.assertEqual(engagement["min_target_range_m"]["value"], 8.0)
            self.assertEqual(engagement["first_interceptor_fuze_time_s"], 2.0)
            self.assertEqual(engagement["closest_approach_event"]["type"], "closest_approach")

            artifacts = {artifact["path"]: artifact for artifact in packet["artifacts"]}
            self.assertEqual(artifacts["report.html"]["kind"], "report")
            self.assertEqual(artifacts["plots/altitude.svg"]["kind"], "plot")
            self.assertEqual(artifacts["plots/altitude.svg"]["url"], "/api/artifacts/mission_alpha/plots/altitude.svg")
            self.assertIn("summary.json", artifacts)

    def test_packet_can_be_limited_to_selected_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._write_minimal_run(Path(tmp) / "selected")

            packet = assemble_report_studio_packet(run_dir, sections=("summary", "artifacts"), max_artifacts=1)

            self.assertEqual(packet["selected_sections"], ["summary", "artifacts"])
            self.assertIn("summary", packet)
            self.assertIn("artifacts", packet)
            self.assertNotIn("events_timeline", packet)
            self.assertNotIn("alarm_summaries", packet)
            self.assertEqual(len(packet["artifacts"]), 1)

    def test_unknown_section_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._write_minimal_run(Path(tmp) / "bad_section")

            with self.assertRaises(ValueError):
                assemble_report_studio_packet(run_dir, sections=("summary", "pdf"))

    def _write_sample_run(self, run_dir: Path) -> Path:
        run_dir.mkdir(parents=True)
        write_json(
            run_dir / "summary.json",
            {
                "scenario": "Mission Alpha",
                "duration_s": 2.0,
                "max_altitude_m": 120.0,
                "max_speed_mps": 82.0,
                "max_load_factor_g": 4.2,
                "min_target_distance_m": 8.0,
                "event_count": 3,
                "final": {
                    "time_s": 2.0,
                    "altitude_m": 90.0,
                    "speed_mps": 70.0,
                    "mass_kg": 9.5,
                    "target_distance_m": 8.0,
                },
            },
        )
        write_json(
            run_dir / "events.json",
            [
                {"time_s": 2.0, "type": "closest_approach", "description": "closest target pass", "miss_distance_m": 8.0},
                {"time_s": 0.5, "type": "launch", "description": "rail clear"},
                {"time_s": 1.4, "type": "max_qbar", "description": "peak dynamic pressure", "severity": "warning"},
            ],
        )
        write_csv(
            run_dir / "history.csv",
            [
                {
                    "time_s": 0.0,
                    "altitude_m": 10.0,
                    "speed_mps": 35.0,
                    "qbar_pa": 12000.0,
                    "load_factor_g": 1.0,
                    "target_range_m": 40.0,
                    "interceptor_range_m": 55.0,
                    "interceptor_fuzed": 0.0,
                    "thrust_n": 100.0,
                    "mass_kg": 10.0,
                },
                {
                    "time_s": 1.0,
                    "altitude_m": 120.0,
                    "speed_mps": 82.0,
                    "qbar_pa": 65000.0,
                    "load_factor_g": 4.2,
                    "target_range_m": 18.0,
                    "interceptor_range_m": 22.0,
                    "interceptor_fuzed": 0.0,
                    "thrust_n": 80.0,
                    "mass_kg": 9.7,
                },
                {
                    "time_s": 2.0,
                    "altitude_m": 90.0,
                    "speed_mps": 70.0,
                    "qbar_pa": 52000.0,
                    "load_factor_g": 2.5,
                    "target_range_m": 8.0,
                    "interceptor_range_m": 9.0,
                    "interceptor_fuzed": 1.0,
                    "thrust_n": 0.0,
                    "mass_kg": 9.5,
                },
            ],
        )
        write_csv(run_dir / "controls.csv", [{"time_s": 0.0, "throttle": 0.9}, {"time_s": 2.0, "throttle": 0.5}])
        write_csv(run_dir / "sensors.csv", [{"time_s": 0.0, "gps_valid": 1.0}, {"time_s": 2.0, "gps_valid": 0.0}])
        write_csv(run_dir / "targets.csv", [{"time_s": 0.0, "target_id": "target-a"}])
        write_csv(run_dir / "interceptors.csv", [{"time_s": 0.0, "interceptor_id": "int-1"}])
        (run_dir / "report.html").write_text("<html>report</html>")
        (run_dir / "plots").mkdir()
        (run_dir / "plots" / "altitude.svg").write_text("<svg></svg>")
        return run_dir

    def _write_minimal_run(self, run_dir: Path) -> Path:
        run_dir.mkdir(parents=True)
        write_json(run_dir / "summary.json", {"scenario": "Selected", "duration_s": 1.0})
        (run_dir / "report.html").write_text("<html>report</html>")
        return run_dir


if __name__ == "__main__":
    unittest.main()
