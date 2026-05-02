from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aerosim6dof.analysis.scenario_validation import ScenarioAdvisory, validate_scenario_advisories


def codes(advisories: list[ScenarioAdvisory]) -> set[str]:
    return {item.code for item in advisories}


class ScenarioValidationHardeningTests(unittest.TestCase):
    def test_reference_resolution_reports_existing_and_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "vehicles").mkdir()
            (base / "vehicles" / "small.json").write_text("{}")
            scenario = {
                "vehicle_config": "vehicles/small.json",
                "environment_config": "environments/missing.json",
                "sensors": {"radar_altimeter": {"config_path": "radar.json"}},
                "initial": {"position_m": [0.0, 0.0, 100.0], "velocity_mps": [50.0, 0.0, 0.0]},
                "events": {"qbar_limit_pa": 90000.0, "load_limit_g": 12.0},
            }

            advisories = validate_scenario_advisories(scenario, base_dir=base)
            by_path = {item.path: item for item in advisories if item.code.startswith("REFERENCE_")}

            self.assertEqual(by_path["vehicle_config"].code, "REFERENCE_RESOLVED")
            self.assertTrue(by_path["vehicle_config"].resolved_reference.endswith("vehicles/small.json"))
            self.assertEqual(by_path["environment_config"].code, "REFERENCE_MISSING")
            self.assertEqual(by_path["sensors.radar_altimeter.config_path"].code, "REFERENCE_MISSING")

    def test_incomplete_extreme_dict_returns_warnings_without_crashing(self) -> None:
        scenario = {
            "dt": 0.25,
            "duration": 0.5,
            "initial": {
                "position_m": [0.0, 0.0, 42000.0],
                "velocity_mps": [1250.0, 0.0, 0.0],
                "euler_deg": [0.0, 75.0, 0.0],
            },
            "guidance": {"throttle": 1.2},
            "vehicle": {"mass_kg": 10.0, "dry_mass_kg": 12.0},
        }

        advisories = validate_scenario_advisories(scenario)
        found = codes(advisories)

        self.assertIn("MISSING_ENVIRONMENT_MODEL", found)
        self.assertIn("AUTOPILOT_DEFAULTS_IMPLICIT", found)
        self.assertIn("TIMESTEP_COARSE", found)
        self.assertIn("STEP_COUNT_LOW", found)
        self.assertIn("INITIAL_ALTITUDE_EXTREME", found)
        self.assertIn("INITIAL_SPEED_EXTREME", found)
        self.assertIn("THROTTLE_OUT_OF_RANGE", found)
        self.assertIn("VEHICLE_MASS_INCONSISTENT", found)
        self.assertIn("MISSING_TERMINATION_SECTION", found)
        self.assertIn("MISSING_OUTPUT_SECTION", found)
        self.assertTrue(all(item.path and item.message for item in advisories))

    def test_engagement_and_terrain_radar_mismatches_are_advisory_only(self) -> None:
        scenario = {
            "vehicle_config": "../vehicles/baseline.json",
            "environment": {
                "terrain": {"enabled": False, "type": "plane", "base_altitude_m": 15.0},
                "ground_contact": {"enabled": True},
            },
            "initial": {"position_m": [0.0, 0.0, 8.0], "velocity_mps": [40.0, 0.0, 0.0]},
            "guidance": {"mode": "target_intercept"},
            "targets": [{"id": "target_a"}, {"id": "target_a"}],
            "interceptors": [{"target_id": "missing_target"}],
            "sensors": {
                "radar_altimeter": {"enabled": True, "min_altitude_m": 100.0, "max_altitude_m": 50.0}
            },
            "events": {"qbar_limit_pa": 100000.0},
        }

        found = codes(validate_scenario_advisories(scenario))

        self.assertIn("TERRAIN_DISABLED_WITH_SETTINGS", found)
        self.assertIn("GROUND_CONTACT_WITH_DISABLED_TERRAIN", found)
        self.assertIn("RADAR_WITH_DISABLED_TERRAIN", found)
        self.assertIn("RADAR_RANGE_INVERTED", found)
        self.assertIn("TARGET_ID_DUPLICATE", found)
        self.assertIn("INTERCEPTOR_TARGET_UNKNOWN", found)
        self.assertIn("TARGET_THRESHOLD_MISSING", found)

    def test_json_file_input_infers_reference_base_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "vehicle.json").write_text("{}")
            scenario_path = base / "scenario.json"
            scenario_path.write_text(
                json.dumps(
                    {
                        "vehicle_config": "vehicle.json",
                        "environment_config": "missing_env.json",
                        "initial": {"position_m": [0.0, 0.0, 20.0], "velocity_mps": [30.0, 0.0, 0.0]},
                        "events": {"qbar_limit_pa": 90000.0, "load_limit_g": 12.0},
                    }
                )
            )

            advisories = validate_scenario_advisories(scenario_path)
            reference_codes = {(item.path, item.code) for item in advisories if item.code.startswith("REFERENCE_")}

            self.assertIn(("vehicle_config", "REFERENCE_RESOLVED"), reference_codes)
            self.assertIn(("environment_config", "REFERENCE_MISSING"), reference_codes)

    def test_json_text_and_bad_input_are_defensive(self) -> None:
        advisories = validate_scenario_advisories('{"initial": {"position_m": [0, 0, 1]}}')
        self.assertIn("MISSING_VEHICLE_MODEL", codes(advisories))

        invalid = validate_scenario_advisories("[1, 2, 3]")
        self.assertEqual(invalid[0].code, "SCENARIO_TOP_LEVEL_NOT_OBJECT")


if __name__ == "__main__":
    unittest.main()
