from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from aerosim6dof.analysis.examples_gallery import build_examples_gallery


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class ExamplesGalleryTests(unittest.TestCase):
    def make_examples_root(self, temp_dir: str) -> Path:
        examples_root = Path(temp_dir) / "examples"
        (examples_root / "scenarios").mkdir(parents=True)
        return examples_root

    def cards_by_id(self, examples_root: Path) -> dict[str, dict]:
        return {card["id"]: card for card in build_examples_gallery(examples_root)}

    def test_metadata_matching_for_nominal_and_target_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            examples_root = self.make_examples_root(temp_dir)
            scenarios = examples_root / "scenarios"
            write_json(
                scenarios / "nominal_ascent.json",
                {
                    "name": "nominal_ascent",
                    "duration": 18.0,
                    "dt": 0.03,
                    "initial": {"position_m": [0.0, 0.0, 20.0]},
                    "guidance": {"mode": "pitch_program"},
                },
            )
            write_json(
                scenarios / "target_intercept.json",
                {
                    "name": "target_intercept",
                    "duration": 12.0,
                    "dt": 0.02,
                    "initial": {"position_m": [0.0, 0.0, 100.0]},
                    "guidance": {"mode": "target_intercept"},
                    "targets": [{"id": "target"}],
                    "interceptors": [{"id": "interceptor", "target_id": "target"}],
                },
            )

            cards = self.cards_by_id(examples_root)

        self.assertEqual(cards["nominal_ascent"]["title"], "Nominal Ascent")
        self.assertEqual(cards["nominal_ascent"]["category"], "Baseline")
        self.assertEqual(cards["nominal_ascent"]["difficulty"], "Beginner")
        self.assertIn("baseline", cards["nominal_ascent"]["tags"])
        self.assertIn("pitch_deg", cards["nominal_ascent"]["primary_metrics"])
        self.assertIn("pitch-program", cards["nominal_ascent"]["tags"])
        self.assertIn("pitch-program", cards["nominal_ascent"]["suggested_next_edit"])
        self.assertEqual(cards["nominal_ascent"]["run_payload"], {"action": "run", "params": {"scenario_id": "nominal_ascent"}})
        self.assertEqual(cards["nominal_ascent"]["clone_payload"]["source_scenario_id"], "nominal_ascent")
        self.assertEqual(cards["nominal_ascent"]["clone_payload"]["scenario_path"], "examples/scenarios/nominal_ascent.json")
        self.assertEqual(cards["nominal_ascent"]["edit_payload"]["scenario_id"], "nominal_ascent")
        self.assertTrue(cards["nominal_ascent"]["can_run"])
        self.assertEqual(cards["target_intercept"]["title"], "Target Intercept")
        self.assertEqual(cards["target_intercept"]["category"], "Engagement")
        self.assertIn("intercept", cards["target_intercept"]["tags"])
        self.assertIn("target_distance_m", cards["target_intercept"]["primary_metrics"])

    def test_invalid_json_becomes_non_runnable_fallback_card(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            examples_root = self.make_examples_root(temp_dir)
            (examples_root / "scenarios" / "broken_case.json").write_text("{ invalid", encoding="utf-8")

            cards = self.cards_by_id(examples_root)

        broken = cards["broken_case"]
        self.assertEqual(broken["title"], "Broken Case")
        self.assertFalse(broken["can_run"])
        self.assertTrue(any("Invalid JSON" in note for note in broken["notes"]))
        self.assertEqual(broken["scenario_path"], "examples/scenarios/broken_case.json")

    def test_unknown_valid_scenario_gets_fallback_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            examples_root = self.make_examples_root(temp_dir)
            write_json(
                examples_root / "scenarios" / "custom_loiter_demo.json",
                {
                    "name": "custom_loiter_demo",
                    "duration": 30.0,
                    "dt": 0.05,
                    "vehicle_config": "../vehicles/baseline.json",
                    "environment_config": "../environments/calm.json",
                    "initial": {"position_m": [0.0, 0.0, 500.0]},
                    "guidance": {"mode": "altitude_hold"},
                },
            )

            cards = self.cards_by_id(examples_root)

        card = cards["custom_loiter_demo"]
        self.assertEqual(card["title"], "Custom Loiter Demo")
        self.assertEqual(card["category"], "Guidance")
        self.assertIn("altitude-hold", card["tags"])
        self.assertEqual(card["difficulty"], "Intermediate")
        self.assertIn("summary.json", card["expected_outputs"])
        self.assertEqual(card["run_payload"]["params"], {"scenario_id": "custom_loiter_demo"})
        self.assertEqual(card["clone_payload"]["suggested_name"], "custom_loiter_demo_copy")
        self.assertIn("altitude hold", card["suggested_next_edit"])
        self.assertTrue(card["can_run"])
        self.assertTrue(all(not Path(card["scenario_path"]).is_absolute() for card in cards.values()))

    def test_checked_in_scenarios_have_stable_curated_cards_without_outputs(self) -> None:
        scenario_ids = {path.stem for path in Path("examples/scenarios").glob("*.json")}
        cards = self.cards_by_id(Path("examples"))

        self.assertEqual(set(cards), scenario_ids)
        self.assertGreaterEqual(len(cards), 10)
        for scenario_id, card in cards.items():
            self.assertEqual(card["id"], scenario_id)
            self.assertEqual(card["scenario_path"], f"examples/scenarios/{scenario_id}.json")
            self.assertTrue(card["category"])
            self.assertTrue(card["description"])
            self.assertTrue(card["suggested_next_edit"])
            self.assertTrue(card["expected_outputs"])
            self.assertEqual(card["run_payload"]["params"]["scenario_id"], scenario_id)
            self.assertEqual(card["clone_payload"]["source_scenario_id"], scenario_id)
            self.assertEqual(card["edit_payload"]["scenario_path"], card["scenario_path"])
            self.assertNotIn("outputs/", " ".join(card["expected_outputs"]))

    def test_weird_scenario_shape_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            examples_root = self.make_examples_root(temp_dir)
            write_json(examples_root / "scenarios" / "list_shape.json", ["not", "a", "scenario"])
            write_json(examples_root / "scenarios" / "missing_blocks.json", {"name": "missing_blocks"})

            cards = self.cards_by_id(examples_root)

        self.assertFalse(cards["list_shape"]["can_run"])
        self.assertTrue(any("object" in note for note in cards["list_shape"]["notes"]))
        self.assertFalse(cards["missing_blocks"]["can_run"])
        self.assertTrue(any("duration" in note for note in cards["missing_blocks"]["notes"]))

    def test_unsafe_scenario_symlink_is_skipped(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlink is unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            examples_root = self.make_examples_root(temp_dir)
            outside = Path(temp_dir) / "outside.json"
            write_json(outside, {"name": "outside"})
            try:
                os.symlink(outside, examples_root / "scenarios" / "escaped.json")
            except OSError as exc:
                self.skipTest(f"symlink creation failed: {exc}")

            cards = self.cards_by_id(examples_root)

        self.assertNotIn("escaped", cards)

    def test_missing_examples_root_returns_empty_gallery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cards = build_examples_gallery(Path(temp_dir) / "missing_examples")

        self.assertEqual(cards, [])


if __name__ == "__main__":
    unittest.main()
