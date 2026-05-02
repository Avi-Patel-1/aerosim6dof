import shutil
import tempfile
import unittest
from pathlib import Path

from aerosim6dof.analysis.missile_engagement_compare import build_missile_engagement_comparison, is_missile_showcase_run
from aerosim6dof.reports.csv_writer import write_csv
from aerosim6dof.reports.json_writer import write_json

try:
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError):  # pragma: no cover - optional web dependency
    TestClient = None


class MissileEngagementComparisonTests(unittest.TestCase):
    def test_packet_compares_existing_missile_outputs_side_by_side(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = _write_missile_run(root / "missile_head_on_showcase", "missile_head_on_showcase", miss=4.5, saturated=True)
            run_b = _write_missile_run(root / "missile_crossing_showcase", "missile_crossing_showcase", miss=12.0, saturated=False)

            packet = build_missile_engagement_comparison([run_a, run_b], run_ids=["a", "b"], max_samples=3)

            self.assertEqual(packet["schema"], "aerosim6dof.missile_engagement_comparison.v1")
            self.assertEqual(packet["run_count"], 2)
            self.assertEqual([row["id"] for row in packet["comparison_table"]], ["a", "b"])
            self.assertEqual(packet["comparison_table"][0]["miss_distance_m"], 4.5)
            self.assertEqual(packet["comparison_table"][0]["first_seeker_lock_time_s"], 0.2)
            self.assertAlmostEqual(packet["comparison_table"][0]["seeker_lock_fraction"], 0.75)
            self.assertEqual(packet["comparison_table"][0]["first_fuze_time_s"], 0.6)
            self.assertEqual(packet["comparison_table"][0]["actuator_saturation_count"], 1)
            self.assertAlmostEqual(packet["comparison_table"][0]["actuator_saturation_fraction"], 0.25)
            self.assertIn("boost", packet["comparison_table"][0]["motor_phases"])
            self.assertIn("range_rate_mps", packet["runs"][0]["range"]["timeline"][0])
            self.assertEqual(packet["runs"][0]["motor"]["phase_intervals"][0]["value"], "idle")
            self.assertEqual(packet["runs"][0]["fuze"]["state_intervals"][-1]["value"], "detonated")
            self.assertIn("closest_approach_timeline", packet["runs"][0])
            self.assertLessEqual(len(packet["runs"][0]["range"]["timeline"]), 4)
            self.assertTrue(is_missile_showcase_run(run_a))


@unittest.skipIf(TestClient is None, "FastAPI is not installed")
class MissileEngagementComparisonApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from aerosim6dof.web import api

        self.api = api
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.outputs_dir = self.root / "outputs"
        self.web_runs_dir = self.outputs_dir / "web_runs"
        self.scenarios_dir = self.root / "examples" / "scenarios"
        self.original_outputs_dir = api.OUTPUTS_DIR
        self.original_web_runs_dir = api.WEB_RUNS_DIR
        self.original_scenarios_dir = api.SCENARIOS_DIR
        self.original_seed_started = api.SEED_SUITE_STARTED
        api.OUTPUTS_DIR = self.outputs_dir
        api.WEB_RUNS_DIR = self.web_runs_dir
        api.SCENARIOS_DIR = self.scenarios_dir
        api.SEED_SUITE_STARTED = True
        self.run_a = _write_missile_run(self.outputs_dir / "web_runs" / "seed_scenario_suite" / "missile_head_on_showcase", "missile_head_on_showcase", miss=4.5)
        self.run_b = _write_missile_run(self.outputs_dir / "web_runs" / "seed_scenario_suite" / "missile_tail_chase_showcase", "missile_tail_chase_showcase", miss=18.0)
        _write_non_missile_run(self.outputs_dir / "web_runs" / "seed_scenario_suite" / "nominal_ascent")
        self.client = TestClient(api.create_app())

    def tearDown(self) -> None:
        api = self.api
        api.OUTPUTS_DIR = self.original_outputs_dir
        api.WEB_RUNS_DIR = self.original_web_runs_dir
        api.SCENARIOS_DIR = self.original_scenarios_dir
        api.SEED_SUITE_STARTED = self.original_seed_started
        shutil.rmtree(self.web_runs_dir, ignore_errors=True)
        self.temp_dir.cleanup()

    def test_route_discovers_missile_showcase_runs_and_supports_explicit_ids(self) -> None:
        discovered = self.client.get("/api/missile-engagement-comparison?max_samples=20")

        self.assertEqual(discovered.status_code, 200, discovered.text)
        payload = discovered.json()
        self.assertEqual(payload["run_count"], 2)
        scenarios = {row["scenario"] for row in payload["comparison_table"]}
        self.assertEqual(scenarios, {"missile_head_on_showcase", "missile_tail_chase_showcase"})
        self.assertNotIn("nominal_ascent", scenarios)
        self.assertIn("miss_distance_m", payload["timeline_channels"])

        explicit_id = "web_runs~seed_scenario_suite~missile_head_on_showcase"
        explicit = self.client.get(f"/api/missile-engagement-comparison?run_ids={explicit_id}&max_samples=20")
        self.assertEqual(explicit.status_code, 200, explicit.text)
        self.assertEqual(explicit.json()["run_count"], 1)
        self.assertEqual(explicit.json()["comparison_table"][0]["id"], explicit_id)

    def test_capability_action_returns_same_read_only_packet(self) -> None:
        response = self.client.post("/api/actions/missile_engagement_comparison", json={"params": {"max_samples": 20}})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["action"], "missile_engagement_comparison")
        self.assertIsNone(payload["output_id"])
        self.assertEqual(payload["data"]["run_count"], 2)


def _write_missile_run(run_dir: Path, scenario: str, *, miss: float, saturated: bool = False) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "summary.json",
        {
            "scenario": scenario,
            "samples": 4,
            "min_interceptor_range_m": miss,
            "interceptor_fuze_count": 1,
        },
    )
    write_json(
        run_dir / "events.json",
        [
            {"time_s": 0.6, "type": "interceptor_fuze", "miss_distance_m": miss, "target_id": "target", "interceptor_id": "missile"},
            {"time_s": 0.6, "type": "interceptor_closest_approach", "miss_distance_m": miss, "target_id": "target", "interceptor_id": "missile"},
            {"time_s": 0.4, "type": "actuator_saturation", "description": "control saturated"},
        ],
    )
    rows = [
        _missile_row(0.0, 100.0, 0.0, "idle", "safe", False, False, False, miss + 20.0),
        _missile_row(0.2, 60.0, 1.0, "boost", "armed", True, False, False, miss + 10.0),
        _missile_row(0.4, 20.0, 8.0, "boost", "armed", True, saturated, False, miss + 2.0),
        _missile_row(0.6, miss, 5.0, "sustain", "detonated", True, False, True, miss),
    ]
    write_csv(run_dir / "history.csv", rows)
    write_csv(run_dir / "interceptors.csv", rows)
    return run_dir


def _missile_row(
    time_s: float,
    range_m: float,
    lateral_accel: float,
    motor_phase: str,
    fuze_status: str,
    locked: bool,
    saturated: bool,
    fuzed: bool,
    best_miss: float,
) -> dict[str, object]:
    return {
        "time_s": time_s,
        "interceptor_id": "missile",
        "interceptor_target_id": "target",
        "interceptor_range_m": range_m,
        "interceptor_range_rate_mps": -100.0,
        "interceptor_best_miss_m": best_miss,
        "altitude_agl_m": 1000.0,
        "altitude_agl_rate_mps": 0.0,
        "terrain_elevation_m": 0.0,
        "ground_contact": 0.0,
        "impact_speed_mps": 0.0,
        "target_range_m": range_m,
        "closing_speed_mps": 100.0,
        "missile_mode": 1.0,
        "seeker_valid": 1.0 if locked else 0.0,
        "missile_seeker_status": "valid" if locked else "search",
        "missile_seeker_range_m": range_m,
        "missile_guidance_valid": 1.0 if locked else 0.0,
        "missile_closing_speed_mps": 100.0,
        "missile_motor_thrust_n": 1000.0 if motor_phase == "boost" else 200.0,
        "missile_motor_spool_fraction": 1.0 if motor_phase else 0.0,
        "missile_motor_phase": motor_phase,
        "missile_lateral_accel_mps2": lateral_accel,
        "missile_control_saturated": 1.0 if saturated else 0.0,
        "missile_fuze_armed": 1.0 if fuze_status != "safe" else 0.0,
        "missile_fuzed": 1.0 if fuzed else 0.0,
        "missile_fuze_status": fuze_status,
        "missile_fuze_closest_range_m": best_miss,
    }


def _write_non_missile_run(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "summary.json", {"scenario": "nominal_ascent"})
    write_csv(run_dir / "history.csv", [{"time_s": 0.0, "altitude_m": 100.0}])
    return run_dir


if __name__ == "__main__":
    unittest.main()
