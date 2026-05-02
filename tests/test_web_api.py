import shutil
import tempfile
import time
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError):  # pragma: no cover - optional web dependency
    TestClient = None


@unittest.skipIf(TestClient is None, "FastAPI is not installed")
class WebApiTests(unittest.TestCase):
    def setUp(self):
        from aerosim6dof.web.api import app

        self.client = TestClient(app)

    def test_lists_scenarios_runs_and_telemetry(self):
        scenarios = self.client.get("/api/scenarios")
        self.assertEqual(scenarios.status_code, 200)
        ids = {item["id"] for item in scenarios.json()}
        self.assertIn("nominal_ascent", ids)

        runs = self.client.get("/api/runs")
        self.assertEqual(runs.status_code, 200)
        run_items = runs.json()
        self.assertGreater(len(run_items), 0)
        run_id = run_items[0]["id"]

        detail = self.client.get(f"/api/runs/{run_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("artifacts", detail.json())

        telemetry = self.client.get(f"/api/runs/{run_id}/telemetry?stride=25")
        self.assertEqual(telemetry.status_code, 200)
        payload = telemetry.json()
        self.assertGreater(payload["sample_count"], 0)
        self.assertIn("time_s", payload["channels"]["history"])
        self.assertEqual(payload["metadata"]["altitude_m"]["display_name"], "Altitude")
        self.assertEqual(payload["metadata"]["speed_mps"]["unit"], "m/s")
        self.assertEqual(payload["metadata"]["qbar_pa"]["group"], "Aerodynamics")
        self.assertEqual(payload["metadata"]["load_factor_g"]["role"], "aero")
        self.assertEqual(payload["metadata"]["pitch_deg"]["group"], "Attitude")

        alarms = self.client.get(f"/api/runs/{run_id}/alarms")
        self.assertEqual(alarms.status_code, 200)
        self.assertIsInstance(alarms.json(), list)

    def test_validate_and_create_web_run(self):
        from aerosim6dof.web import api

        run_root = api.OUTPUTS_DIR / "web_runs_test_api"
        original = api.WEB_RUNS_DIR
        api.WEB_RUNS_DIR = run_root
        shutil.rmtree(run_root, ignore_errors=True)
        try:
            validation = self.client.post("/api/validate", json={"scenario_id": "nominal_ascent"})
            self.assertEqual(validation.status_code, 200)
            self.assertTrue(validation.json()["valid"])

            created = self.client.post(
                "/api/runs",
                json={"scenario_id": "nominal_ascent", "run_name": "api smoke"},
            )
            self.assertEqual(created.status_code, 200)
            run_id = created.json()["id"]
            self.assertTrue(run_id.startswith("web_runs_test_api~"))

            telemetry = self.client.get(f"/api/runs/{run_id}/telemetry?stride=50")
            self.assertEqual(telemetry.status_code, 200)
            self.assertGreater(len(telemetry.json()["history"]), 0)
        finally:
            api.WEB_RUNS_DIR = original
            shutil.rmtree(run_root, ignore_errors=True)

    def test_scenario_detail_draft_and_job(self):
        from aerosim6dof.web import api

        run_root = api.OUTPUTS_DIR / "web_draft_test_api"
        original = api.WEB_RUNS_DIR
        api.WEB_RUNS_DIR = run_root
        shutil.rmtree(run_root, ignore_errors=True)
        try:
            detail = self.client.get("/api/scenarios/nominal_ascent")
            self.assertEqual(detail.status_code, 200)
            raw = detail.json()["raw"]
            self.assertEqual(raw["name"], "nominal_ascent")

            draft = self.client.post("/api/scenario-drafts", json={"scenario": raw, "name": "api draft"})
            self.assertEqual(draft.status_code, 200)
            draft_payload = draft.json()
            self.assertTrue(draft_payload["valid"])
            self.assertTrue(draft_payload["path"].startswith("outputs/web_draft_test_api/scenario_drafts/"))

            job = self.client.post("/api/jobs/inspect_vehicle", json={"params": {"vehicle_id": "baseline"}})
            self.assertEqual(job.status_code, 200)
            job_id = job.json()["id"]
            final = None
            for _ in range(20):
                response = self.client.get(f"/api/jobs/{job_id}")
                self.assertEqual(response.status_code, 200)
                final = response.json()
                if final["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.05)
            self.assertIsNotNone(final)
            self.assertEqual(final["status"], "completed")
            self.assertEqual(final["progress"], 1.0)
            self.assertGreaterEqual(len(final["events"]), 3)
            self.assertIn("reading model data", {event["message"] for event in final["events"]})
            self.assertEqual(final["result"]["data"]["name"], "baseline_research_vehicle")

            jobs = self.client.get("/api/jobs")
            self.assertEqual(jobs.status_code, 200)
            self.assertTrue(any(item["id"] == job_id for item in jobs.json()))

            events = self.client.get(f"/api/jobs/{job_id}/events")
            self.assertEqual(events.status_code, 200)
            self.assertIn("data:", events.text)
            self.assertIn('"status":"completed"', events.text)
        finally:
            api.WEB_RUNS_DIR = original
            shutil.rmtree(run_root, ignore_errors=True)

    def test_capabilities_and_actions(self):
        from aerosim6dof.web import api

        run_root = api.OUTPUTS_DIR / "web_actions_test_api"
        original = api.WEB_RUNS_DIR
        api.WEB_RUNS_DIR = run_root
        shutil.rmtree(run_root, ignore_errors=True)
        try:
            capabilities = self.client.get("/api/capabilities")
            self.assertEqual(capabilities.status_code, 200)
            names = {item["id"] for item in capabilities.json()}
            self.assertIn("monte_carlo", names)
            self.assertIn("linear_model_report", names)

            trim = self.client.post(
                "/api/actions/trim",
                json={"params": {"vehicle_id": "baseline", "speed_mps": 120.0, "altitude_m": 1000.0}},
            )
            self.assertEqual(trim.status_code, 200)
            payload = trim.json()
            self.assertEqual(payload["action"], "trim")
            self.assertTrue(payload["output_id"].startswith("web_actions_test_api~"))
            self.assertTrue(any(artifact["name"] == "trim.json" for artifact in payload["artifacts"]))

            inspect = self.client.post("/api/actions/inspect_vehicle", json={"params": {"vehicle_id": "baseline"}})
            self.assertEqual(inspect.status_code, 200)
            self.assertEqual(inspect.json()["data"]["name"], "baseline_research_vehicle")
        finally:
            api.WEB_RUNS_DIR = original
            shutil.rmtree(run_root, ignore_errors=True)

    def test_artifact_paths_are_limited_to_run_directory(self):
        blocked = self.client.get("/api/artifacts/batch_after_damping~nominal_ascent/../summary.json")
        self.assertEqual(blocked.status_code, 404)

    def test_telemetry_metadata_fallback_for_unknown_channels(self):
        from aerosim6dof.telemetry.metadata import metadata_for_channels

        metadata = metadata_for_channels({"history": ["custom_rate_mps"], "sensors": ["mystery_valid"]})
        self.assertEqual(metadata["custom_rate_mps"]["display_name"], "Custom Rate")
        self.assertEqual(metadata["custom_rate_mps"]["unit"], "m/s")
        self.assertEqual(metadata["custom_rate_mps"]["group"], "Unknown")
        self.assertEqual(metadata["mystery_valid"]["source"], "sensors")
        self.assertEqual(metadata["mystery_valid"]["role"], "sensor")

    def test_seed_suite_requires_current_history_schema(self):
        from aerosim6dof.web import api

        original_outputs = api.OUTPUTS_DIR
        original_web_runs = api.WEB_RUNS_DIR
        original_scenarios = api.SCENARIOS_DIR
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outputs = root / "outputs"
            web_runs = outputs / "web_runs"
            scenarios = root / "scenarios"
            seed_suite = web_runs / "seed_scenario_suite"
            run_dir = seed_suite / "nominal_ascent"
            scenarios.mkdir(parents=True)
            run_dir.mkdir(parents=True)
            (scenarios / "nominal_ascent.json").write_text("{}")
            (seed_suite / ".seed_complete.json").write_text('{"scenario_count": 1}')
            (run_dir / "summary.json").write_text("{}")
            (run_dir / "history.csv").write_text("time_s,altitude_m\n0,10\n")

            api.OUTPUTS_DIR = outputs
            api.WEB_RUNS_DIR = web_runs
            api.SCENARIOS_DIR = scenarios
            try:
                self.assertFalse(api._seed_suite_ready())
                self.assertEqual(api._find_run_dirs(), [])

                (run_dir / "history.csv").write_text("time_s,altitude_m,terrain_elevation_m,altitude_agl_m\n0,10,2,8\n")
                self.assertTrue(api._seed_suite_ready())
                self.assertEqual(api._find_run_dirs(), [run_dir])
            finally:
                api.OUTPUTS_DIR = original_outputs
                api.WEB_RUNS_DIR = original_web_runs
                api.SCENARIOS_DIR = original_scenarios


if __name__ == "__main__":
    unittest.main()
