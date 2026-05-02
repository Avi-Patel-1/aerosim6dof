import shutil
import unittest

try:
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError):  # pragma: no cover - optional web dependency
    TestClient = None


@unittest.skipIf(TestClient is None, "FastAPI is not installed")
class ScenarioBuilderApiTests(unittest.TestCase):
    def setUp(self):
        from aerosim6dof.web.api import app

        self.client = TestClient(app)

    def _rich_draft(self):
        from aerosim6dof.web import api

        draft = api.load_json(api.SCENARIOS_DIR / "target_intercept.json")
        draft["name"] = "scenario_builder_rich_draft"
        draft["vehicle_config"] = "../vehicles/baseline.json"
        draft["environment_config"] = "../environments/gusted_range.json"
        draft["sensors"] = {
            "seed": 4242,
            "imu": {"rate_hz": 100.0, "gyro_noise_std_dps": 0.02},
            "gps": {"rate_hz": 5.0, "position_noise_std_m": 2.0},
            "barometer": {"rate_hz": 20.0, "noise_std_m": 1.5},
            "faults": [
                {
                    "sensor": "gps",
                    "type": "dropout",
                    "start_s": 4.0,
                    "end_s": 5.5,
                }
            ],
        }
        return draft

    def test_validate_accepts_rich_scenario_builder_draft(self):
        response = self.client.post("/api/validate", json={"scenario": self._rich_draft()})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["scenario"], "scenario_builder_rich_draft")
        self.assertEqual(payload["dt"], 0.03)
        self.assertEqual(payload["duration"], 18.0)
        self.assertIn("summary", payload)
        self.assertIn("warnings", payload)
        self.assertIn("explanation", payload)
        self.assertIn("recommendations", payload)
        self.assertEqual(payload["summary"]["counts"]["targets"], 2)
        self.assertTrue(any("target_id" in item for item in payload["recommendations"]))

    def test_scenario_drafts_stores_valid_rich_draft_under_configured_web_runs(self):
        from aerosim6dof.web import api

        run_root = api.OUTPUTS_DIR / "web_scenario_builder_drafts_test"
        original = api.WEB_RUNS_DIR
        api.WEB_RUNS_DIR = run_root
        shutil.rmtree(run_root, ignore_errors=True)
        try:
            response = self.client.post(
                "/api/scenario-drafts",
                json={"scenario": self._rich_draft(), "name": "Scenario Builder Rich Draft"},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["valid"])
            self.assertEqual(payload["name"], "scenario_builder_rich_draft")
            self.assertTrue(payload["path"].startswith("outputs/web_scenario_builder_drafts_test/scenario_drafts/"))

            draft_path = api.ROOT / payload["path"]
            self.assertTrue(draft_path.is_file())
            self.assertTrue(draft_path.resolve().is_relative_to((run_root / "scenario_drafts").resolve()))
            self.assertEqual(api.load_json(draft_path)["targets"][0]["id"], "primary_target")
        finally:
            api.WEB_RUNS_DIR = original
            shutil.rmtree(run_root, ignore_errors=True)

    def test_create_run_target_intercept_returns_engagement_and_interceptor_artifacts(self):
        from aerosim6dof.web import api

        run_root = api.OUTPUTS_DIR / "web_scenario_builder_runs_test"
        original = api.WEB_RUNS_DIR
        api.WEB_RUNS_DIR = run_root
        shutil.rmtree(run_root, ignore_errors=True)
        try:
            response = self.client.post(
                "/api/runs",
                json={"scenario_id": "target_intercept", "run_name": "scenario builder intercept"},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["id"].startswith("web_scenario_builder_runs_test~"))
            self.assertEqual(payload["scenario"], "target_intercept")
            self.assertIn("min_target_range_m", payload["summary"])
            self.assertIn("min_interceptor_range_m", payload["summary"])
            self.assertIn("interceptor_fuze_count", payload["summary"])
            self.assertIn("interceptor_fuzed", payload["summary"]["final"])
            self.assertIn("interceptor_id", payload["summary"]["final"])
            self.assertIn("interceptor_range_m", payload["summary"]["final"])

            artifact_names = {artifact["name"] for artifact in payload["artifacts"]}
            self.assertIn("targets.csv", artifact_names)
            self.assertIn("interceptors.csv", artifact_names)
            self.assertIn("summary.json", artifact_names)

            telemetry = self.client.get(f"/api/runs/{payload['id']}/telemetry?stride=100")
            self.assertEqual(telemetry.status_code, 200)
            telemetry_payload = telemetry.json()
            self.assertIn("interceptors", telemetry_payload["channels"])
            self.assertGreater(len(telemetry_payload["channels"]["interceptors"]), 0)
            self.assertGreater(len(telemetry_payload["interceptors"]), 0)
        finally:
            api.WEB_RUNS_DIR = original
            shutil.rmtree(run_root, ignore_errors=True)

    def test_validate_rejects_invalid_draft_without_server_error(self):
        invalid = self._rich_draft()
        invalid["dt"] = 0.0
        invalid["guidance"]["throttle"] = 1.4
        invalid["interceptors"][0]["initial_velocity_mps"] = [10.0, 0.0]

        response = self.client.post("/api/validate", json={"scenario": invalid})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["valid"])
        self.assertIn("warnings", payload)
        self.assertIn("explanation", payload)
        error_text = "; ".join(payload["errors"])
        self.assertIn("dt must be a positive finite number", error_text)
        self.assertIn("guidance.throttle must be between 0 and 1", error_text)
        self.assertIn("interceptors[0].initial_velocity_mps must have three finite numeric elements", error_text)


if __name__ == "__main__":
    unittest.main()
