from __future__ import annotations

import json
import unittest
from pathlib import Path

from aerosim6dof.analysis.scenario_builder import (
    scenario_builder_explanation,
    scenario_builder_recommendations,
    scenario_builder_summary,
    scenario_builder_warnings,
)


ROOT = Path(__file__).resolve().parents[1]


def load_scenario(name: str) -> dict:
    with (ROOT / "examples" / "scenarios" / f"{name}.json").open() as handle:
        return json.load(handle)


class ScenarioBuilderTests(unittest.TestCase):
    def test_nominal_ascent_summary(self) -> None:
        config = load_scenario("nominal_ascent")

        summary = scenario_builder_summary(config)
        warnings = scenario_builder_warnings(config)

        self.assertEqual(summary["name"], "nominal_ascent")
        self.assertEqual(summary["duration"], 18.0)
        self.assertEqual(summary["dt"], 0.03)
        self.assertEqual(summary["vehicle_config"], "../vehicles/baseline.json")
        self.assertEqual(summary["environment_config"], "../environments/calm.json")
        self.assertEqual(summary["guidance_mode"], "pitch_program")
        self.assertAlmostEqual(summary["initial"]["altitude_m"], 20.0)
        self.assertAlmostEqual(summary["initial"]["speed_mps"], 85.37564055396598)
        self.assertEqual(summary["initial"]["pitch_deg"], 6.0)
        self.assertEqual(summary["initial"]["heading_deg"], 0.0)
        self.assertEqual(summary["counts"], {"targets": 0, "interceptors": 0, "faults": 0})
        self.assertEqual(summary["termination_limits"]["qbar_limit_pa"], 90000.0)
        self.assertEqual(summary["termination_limits"]["load_limit_g"], 15.0)
        self.assertFalse([item for item in warnings if item["severity"] == "warning"])

    def test_target_intercept_links_and_text(self) -> None:
        config = load_scenario("target_intercept")

        summary = scenario_builder_summary(config)
        warnings = scenario_builder_warnings(config)
        explanation = scenario_builder_explanation(config)
        recommendations = scenario_builder_recommendations(config)

        self.assertEqual(summary["guidance_mode"], "target_intercept")
        self.assertEqual(summary["counts"]["targets"], 2)
        self.assertEqual(summary["counts"]["interceptors"], 1)
        self.assertEqual(summary["termination_limits"]["target_threshold_m"], 75.0)
        self.assertFalse([item for item in warnings if item["severity"] == "warning"])
        self.assertIn("target_intercept runs for 18 s", explanation)
        self.assertIn("2 target(s) and 1 interceptor(s)", explanation)
        self.assertTrue(any("target_id" in item for item in recommendations))

    def test_incomplete_draft_gets_advisory_warnings(self) -> None:
        draft = {
            "name": "draft",
            "duration": -2.0,
            "dt": 0.5,
            "initial": {
                "position_m": [0.0, 0.0, -3.0],
                "velocity_mps": [1.0, 0.0, 0.0],
                "euler_deg": [0.0, 75.0, 720.0],
            },
            "guidance": {"mode": "target_intercept", "throttle": 1.4},
            "targets": [{"id": "real_target"}],
            "interceptors": [{"target_id": "missing_target"}],
            "sensors": {
                "gps": {"rate_hz": -1.0, "position_noise_std_m": -3.0},
                "faults": [{"type": "dropout", "end_s": 1.0, "start_s": 4.0}],
            },
            "events": {"qbar_limit_pa": 300000.0},
        }

        warnings = scenario_builder_warnings(draft)
        paths = {item["path"] for item in warnings}

        self.assertIn("vehicle_config", paths)
        self.assertIn("environment_config", paths)
        self.assertIn("duration", paths)
        self.assertIn("guidance.throttle", paths)
        self.assertIn("interceptors[0].target_id", paths)
        self.assertIn("sensors.gps.rate_hz", paths)
        self.assertIn("sensors.gps.position_noise_std_m", paths)
        self.assertIn("sensors.faults[0]", paths)
        self.assertIn("sensors.faults[0].end_s", paths)
        self.assertIn("events.load_limit_g", paths)
        self.assertIn("events.target_threshold_m", paths)
        self.assertTrue(any(item["severity"] == "warning" for item in warnings))


if __name__ == "__main__":
    unittest.main()
