import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aerosim6dof.reports.csv_writer import write_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.web.storage import STORAGE_ENV_VAR

try:
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError):  # pragma: no cover - optional web dependency
    TestClient = None


@unittest.skipIf(TestClient is None, "FastAPI is not installed")
class WebApiProductionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        from aerosim6dof.web import api

        self.api = api
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.outputs_dir = self.root / "outputs"
        self.web_runs_dir = self.outputs_dir / "web_runs"
        self.storage_dir = self.root / "storage"
        self.examples_dir = self.root / "examples"
        self.scenarios_dir = self.examples_dir / "scenarios"
        self.vehicles_dir = self.examples_dir / "vehicles"
        self.environments_dir = self.examples_dir / "environments"

        self.original_outputs_dir = api.OUTPUTS_DIR
        self.original_web_runs_dir = api.WEB_RUNS_DIR
        self.original_examples_dir = api.EXAMPLES_DIR
        self.original_scenarios_dir = api.SCENARIOS_DIR
        self.original_vehicles_dir = api.VEHICLES_DIR
        self.original_environments_dir = api.ENVIRONMENTS_DIR
        self.original_seed_started = api.SEED_SUITE_STARTED
        self.env_patch = patch.dict(os.environ, {STORAGE_ENV_VAR: str(self.storage_dir)})
        self.env_patch.start()

        api.OUTPUTS_DIR = self.outputs_dir
        api.WEB_RUNS_DIR = self.web_runs_dir
        api.EXAMPLES_DIR = self.examples_dir
        api.SCENARIOS_DIR = self.scenarios_dir
        api.VEHICLES_DIR = self.vehicles_dir
        api.ENVIRONMENTS_DIR = self.environments_dir
        api.SEED_SUITE_STARTED = True
        with api.JOBS_LOCK:
            api.JOBS.clear()
        self._write_examples()
        self.run_dir = self._write_run("prod_runs/navigation_case")
        self.run_id = "prod_runs~navigation_case"
        self.client = TestClient(api.create_app())

    def tearDown(self) -> None:
        api = self.api
        api.OUTPUTS_DIR = self.original_outputs_dir
        api.WEB_RUNS_DIR = self.original_web_runs_dir
        api.EXAMPLES_DIR = self.original_examples_dir
        api.SCENARIOS_DIR = self.original_scenarios_dir
        api.VEHICLES_DIR = self.original_vehicles_dir
        api.ENVIRONMENTS_DIR = self.original_environments_dir
        api.SEED_SUITE_STARTED = self.original_seed_started
        with api.JOBS_LOCK:
            api.JOBS.clear()
        self.env_patch.stop()
        shutil.rmtree(self.web_runs_dir, ignore_errors=True)
        self.temp_dir.cleanup()

    def test_job_cancel_endpoint_marks_running_job_and_exposes_progress(self) -> None:
        job_id = "job-cancel-001"
        now = "2026-01-01T00:00:00Z"
        with self.api.JOBS_LOCK:
            self.api.JOBS[job_id] = {
                "id": job_id,
                "action": "monte_carlo",
                "status": "running",
                "message": "running simulation",
                "progress": 0.42,
                "created_at_utc": now,
                "started_at_utc": now,
                "finished_at_utc": None,
                "events": [{"time_utc": now, "status": "running", "message": "running simulation", "progress": 0.42}],
                "result": None,
            }

        response = self.client.post(
            f"/api/jobs/{job_id}/cancel",
            json={"reason": "operator requested stop", "requested_by": "test"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(set(payload), {"cancel", "job"})
        self.assertEqual(payload["cancel"]["job_id"], job_id)
        self.assertTrue(payload["cancel"]["requested"])
        self.assertEqual(payload["cancel"]["reason"], "operator requested stop")
        self.assertIn("requested_at", payload["cancel"])
        self.assertEqual(payload["job"]["id"], job_id)
        self.assertEqual(payload["job"]["message"], "cancellation requested")

        progress = self.client.get(f"/api/jobs/{job_id}/progress")
        self.assertEqual(progress.status_code, 200, progress.text)
        progress_payload = progress.json()
        self.assertEqual(progress_payload["job_id"], job_id)
        self.assertIn(progress_payload["phase"], {"running", "cancelling", "cancelled"})
        self.assertLessEqual(progress_payload["percent"], 100.0)

    def test_cancel_missing_job_is_404_and_does_not_create_cancellation_state(self) -> None:
        response = self.client.post("/api/jobs/missing-job/cancel", json={"reason": "operator"})

        self.assertEqual(response.status_code, 404, response.text)
        self.assertFalse(self.api.is_cancel_requested("missing-job") if hasattr(self.api, "is_cancel_requested") else False)

    def test_navigation_telemetry_endpoint_returns_estimator_payload(self) -> None:
        response = self.client.get(f"/api/runs/{self.run_id}/navigation?stride=2")

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(set(payload), {"run_id", "rows", "channels", "summary", "metadata"})
        self.assertEqual(payload["run_id"], self.run_id)
        self.assertEqual(payload["summary"]["source"], "sensors_truth")
        self.assertEqual(payload["summary"]["stride"], 2)
        self.assertEqual(payload["summary"]["input_row_count"], 3)
        self.assertEqual(payload["summary"]["row_count"], 2)
        self.assertIn("estimate_altitude_m", {item["key"] for item in payload["channels"]})
        self.assertEqual(payload["metadata"]["estimate_altitude_m"]["display_name"], "Estimate Altitude")
        self.assertIn("estimate_position_error_m", payload["rows"][0])

    def test_estimation_report_action_writes_fusion_artifacts(self) -> None:
        response = self.client.post("/api/actions/estimation_report", json={"params": {"run_id": self.run_id}})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["action"], "estimation_report")
        self.assertEqual(payload["status"], "completed")
        self.assertIn("estimate_position", payload["data"]["available_comparisons"])
        self.assertIn("gnss_position", payload["data"]["available_comparisons"])
        artifacts = {artifact["name"]: artifact for artifact in payload["artifacts"]}
        self.assertIn("estimation_summary.json", artifacts)
        self.assertIn("estimation_metrics.csv", artifacts)
        self.assertIn("residuals.csv", artifacts)
        self.assertIn("estimation_report.html", artifacts)
        self.assertTrue(payload["output_id"].startswith("web_runs~estimation_report_"))

    def test_navigation_telemetry_missing_run_is_404(self) -> None:
        response = self.client.get("/api/runs/missing~run/navigation")

        self.assertEqual(response.status_code, 404, response.text)

    def test_storage_layout_endpoints_round_trip_under_configured_root(self) -> None:
        layout_id = "pilot_primary"
        create = self.client.post(
            f"/api/storage/layouts/{layout_id}",
            json={
                "name": "Pilot Primary",
                "channels": ["altitude_m", "speed_mps"],
                "config": {"kind": "operations-telemetry", "subsystem": "vehicle"},
            },
        )

        self.assertEqual(create.status_code, 200, create.text)
        saved = create.json()
        self.assertEqual(saved["id"], layout_id)
        self.assertEqual(saved["name"], "Pilot Primary")
        self.assertIn("created_at", saved)
        self.assertIn("updated_at", saved)
        self.assertTrue((self.storage_dir / "layouts" / f"{layout_id}.json").exists())

        listed = self.client.get("/api/storage/layouts")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([item["id"] for item in listed.json()], [layout_id])

        fetched = self.client.get(f"/api/storage/layouts/{layout_id}")
        self.assertEqual(fetched.status_code, 200, fetched.text)
        self.assertEqual(fetched.json()["channels"], ["altitude_m", "speed_mps"])

        deleted = self.client.delete(f"/api/storage/layouts/{layout_id}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json(), {"deleted": True, "id": layout_id})
        self.assertEqual(self.client.get(f"/api/storage/layouts/{layout_id}").status_code, 404)

    def test_storage_layout_endpoints_reject_missing_and_unsafe_ids(self) -> None:
        missing = self.client.get("/api/storage/layouts/not_saved")
        self.assertEqual(missing.status_code, 404, missing.text)

        unsafe = self.client.post("/api/storage/layouts/bad..id", json={"name": "bad"})
        self.assertEqual(unsafe.status_code, 400, unsafe.text)
        self.assertFalse((self.storage_dir.parent / "escape.json").exists())

    def test_validate_response_includes_advisory_summary_even_when_hard_validation_fails(self) -> None:
        scenario = {
            "name": "advisory_summary_case",
            "dt": 0.0,
            "duration": 0.0,
            "guidance": {"mode": "target_intercept"},
            "initial": {"position_m": [0.0, 0.0, -10.0], "velocity_mps": [0.0, 0.0, 0.0], "euler_deg": [0.0, 0.0, 0.0]},
            "targets": [],
        }

        response = self.client.post("/api/validate", json={"scenario": scenario})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("advisories", payload)
        self.assertIn("advisory_summary", payload)
        summary = payload["advisory_summary"]
        self.assertGreaterEqual(summary["warning_count"], 1)
        self.assertIn(summary["highest_severity"], {"error", "warning"})
        self.assertIsInstance(summary["suggested_next_actions"], list)

    def test_report_studio_packet_endpoint_is_read_only_and_sections_are_selectable(self) -> None:
        before = sorted(path.relative_to(self.run_dir).as_posix() for path in self.run_dir.rglob("*") if path.is_file())

        response = self.client.get(f"/api/runs/{self.run_id}/report-studio?sections=summary,artifacts")

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["schema"], "aerosim6dof.report_studio.packet.v1")
        self.assertEqual(payload["selected_sections"], ["summary", "artifacts"])
        self.assertEqual(payload["summary"]["data"]["scenario"], "navigation_case")
        artifacts = {artifact["path"]: artifact for artifact in payload["artifacts"]}
        self.assertIn("summary.json", artifacts)
        self.assertEqual(artifacts["summary.json"]["url"], f"/api/artifacts/{self.run_id}/summary.json")
        after = sorted(path.relative_to(self.run_dir).as_posix() for path in self.run_dir.rglob("*") if path.is_file())
        self.assertEqual(after, before)

    def test_report_studio_missing_run_and_bad_sections_are_safe(self) -> None:
        missing = self.client.get("/api/runs/missing~run/report-studio")
        self.assertEqual(missing.status_code, 404, missing.text)

        bad_section = self.client.get(f"/api/runs/{self.run_id}/report-studio?sections=summary,pdf")
        self.assertEqual(bad_section.status_code, 400, bad_section.text)

    def test_examples_gallery_endpoint_returns_cards_and_handles_missing_root(self) -> None:
        response = self.client.get("/api/examples-gallery")

        self.assertEqual(response.status_code, 200, response.text)
        cards = response.json()
        ids = {card["id"] for card in cards}
        self.assertIn("gallery_nominal", ids)
        self.assertIn("gallery_broken", ids)
        nominal = next(card for card in cards if card["id"] == "gallery_nominal")
        self.assertEqual(nominal["scenario_path"], "examples/scenarios/gallery_nominal.json")

        original_examples = self.api.EXAMPLES_DIR
        self.api.EXAMPLES_DIR = self.root / "missing_examples"
        try:
            missing = self.client.get("/api/examples-gallery")
            self.assertEqual(missing.status_code, 200, missing.text)
            self.assertEqual(missing.json(), [])
        finally:
            self.api.EXAMPLES_DIR = original_examples

    def _write_examples(self) -> None:
        self.scenarios_dir.mkdir(parents=True)
        self.vehicles_dir.mkdir(parents=True)
        self.environments_dir.mkdir(parents=True)
        write_json(
            self.scenarios_dir / "gallery_nominal.json",
            {
                "name": "gallery_nominal",
                "duration": 1.0,
                "dt": 0.1,
                "vehicle_config": "../vehicles/baseline.json",
                "environment_config": "../environments/calm.json",
                "initial": {"position_m": [0.0, 0.0, 100.0], "velocity_mps": [20.0, 0.0, 0.0], "euler_deg": [0.0, 0.0, 0.0]},
                "guidance": {"mode": "open_loop", "throttle": 0.2},
                "outputs": {"summary": True},
            },
        )
        (self.scenarios_dir / "gallery_broken.json").write_text("{ invalid", encoding="utf-8")
        write_json(self.vehicles_dir / "baseline.json", {"name": "baseline"})
        write_json(self.environments_dir / "calm.json", {"name": "calm"})

    def _write_run(self, relative_dir: str) -> Path:
        run_dir = self.outputs_dir / relative_dir
        run_dir.mkdir(parents=True)
        write_json(
            run_dir / "summary.json",
            {
                "scenario": "navigation_case",
                "duration_s": 2.0,
                "final_altitude_m": 102.0,
                "max_speed_mps": 23.0,
                "event_count": 1,
            },
        )
        write_json(run_dir / "manifest.json", {"generated_at_utc": "2026-01-01T00:00:00Z"})
        write_json(run_dir / "events.json", [{"time_s": 1.0, "type": "checkpoint", "message": "nominal"}])
        (run_dir / "report.html").write_text("<html><body>navigation_case</body></html>\n", encoding="utf-8")
        write_csv(
            run_dir / "history.csv",
            [
                {"time_s": 0.0, "altitude_m": 100.0, "speed_mps": 20.0, "qbar_pa": 50.0, "load_factor_g": 1.0},
                {"time_s": 1.0, "altitude_m": 101.0, "speed_mps": 22.0, "qbar_pa": 55.0, "load_factor_g": 1.1},
                {"time_s": 2.0, "altitude_m": 102.0, "speed_mps": 23.0, "qbar_pa": 60.0, "load_factor_g": 1.2},
            ],
        )
        write_csv(
            run_dir / "truth.csv",
            [
                {"time_s": 0.0, "x_m": 0.0, "y_m": 0.0, "altitude_m": 100.0, "vx_mps": 20.0, "vy_mps": 0.0, "vz_mps": 0.0},
                {"time_s": 1.0, "x_m": 20.0, "y_m": 0.0, "altitude_m": 101.0, "vx_mps": 21.0, "vy_mps": 0.0, "vz_mps": 1.0},
                {"time_s": 2.0, "x_m": 42.0, "y_m": 0.0, "altitude_m": 102.0, "vx_mps": 22.0, "vy_mps": 0.0, "vz_mps": 1.0},
            ],
        )
        write_csv(
            run_dir / "sensors.csv",
            [
                {"time_s": 0.0, "sensor_time_s": 0.0, "gps_valid": 1.0, "gps_x_m": 0.0, "gps_y_m": 0.0, "gps_z_m": 100.0, "gps_vx_mps": 20.0, "gps_vy_mps": 0.0, "gps_vz_mps": 0.0},
                {"time_s": 1.0, "sensor_time_s": 1.0, "gps_valid": 1.0, "gps_x_m": 20.0, "gps_y_m": 0.0, "gps_z_m": 101.0, "gps_vx_mps": 21.0, "gps_vy_mps": 0.0, "gps_vz_mps": 1.0},
                {"time_s": 2.0, "sensor_time_s": 2.0, "gps_valid": 0.0, "gps_x_m": 42.0, "gps_y_m": 0.0, "gps_z_m": 102.0, "gps_vx_mps": 22.0, "gps_vy_mps": 0.0, "gps_vz_mps": 1.0},
            ],
        )
        return run_dir


if __name__ == "__main__":
    unittest.main()
