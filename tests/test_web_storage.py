import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aerosim6dof.web.storage import (
    DEFAULT_STORAGE_ROOT,
    SAFE_NAMESPACES,
    STORAGE_ENV_VAR,
    STORAGE_MANIFEST_NAME,
    STORAGE_VERSION,
    FileBackedStorage,
    get_storage,
    get_storage_root,
    storage_status,
)


class WebStorageTests(unittest.TestCase):
    def test_safe_namespaces_and_ids_resolve_inside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = FileBackedStorage(root)

            path = storage.json_path("runs", "mission_alpha-01")

            self.assertEqual(path, (root / "runs" / "mission_alpha-01.json").resolve())
            self.assertIn("runs", SAFE_NAMESPACES)
            with self.assertRaises(ValueError):
                storage.json_path("unknown", "mission_alpha")
            for unsafe_id in ("", "../escape", "nested/path", "mission..alpha", ".hidden"):
                with self.subTest(unsafe_id=unsafe_id):
                    with self.assertRaises(ValueError):
                        storage.json_path("runs", unsafe_id)

    def test_json_round_trip_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = FileBackedStorage(tmp)
            payload = {"name": "draft", "values": [1, 2, 3], "nested": {"ok": True}}

            path = storage.write_json("drafts", "draft_001", payload)

            self.assertEqual(path.name, "draft_001.json")
            self.assertEqual(storage.read_json("drafts", "draft_001"), payload)
            manifest = storage.read_json("drafts", "missing", default={"missing": True})
            self.assertEqual(manifest, {"missing": True})
            manifest_path = Path(tmp) / STORAGE_MANIFEST_NAME
            self.assertTrue(manifest_path.exists())
            self.assertEqual(storage.status()["manifest"]["version"], STORAGE_VERSION)

    def test_traversal_rejection_does_not_create_outside_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = FileBackedStorage(root)

            with self.assertRaises(ValueError):
                storage.write_json("runs", "../escape", {"bad": True})

            self.assertFalse((root.parent / "escape.json").exists())

    def test_env_var_root_is_used_by_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {STORAGE_ENV_VAR: tmp}):
                self.assertEqual(get_storage_root(), Path(tmp).resolve())
                storage = get_storage()
                self.assertEqual(storage.root, Path(tmp).resolve())
                self.assertTrue(storage.env_backed)
                status = storage_status()
                self.assertTrue(status["ok"])
                self.assertTrue(status["env_backed"])
                self.assertTrue(status["persistent"])
                self.assertEqual(status["root"], str(Path(tmp).resolve()))

        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_storage_root(), DEFAULT_STORAGE_ROOT.resolve())

    def test_list_and_delete_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = FileBackedStorage(tmp)
            storage.write_json("layouts", "layout_b", {"order": 2})
            storage.write_json("layouts", "layout_a", {"order": 1})
            storage.write_json("reports", "report_a", {"title": "Report"})

            self.assertEqual(storage.list_json("layouts"), ["layout_a", "layout_b"])
            self.assertEqual(storage.list_json("reports"), ["report_a"])
            self.assertTrue(storage.delete_json("layouts", "layout_a"))
            self.assertFalse(storage.delete_json("layouts", "layout_a"))
            self.assertEqual(storage.list_json("layouts"), ["layout_b"])

    def test_layout_crud_helpers_stamp_and_persist_public_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = FileBackedStorage(tmp)

            saved = storage.save_layout(
                "pilot_primary",
                {"name": "Pilot Primary", "panels": [{"metric": "altitude_m"}]},
            )

            self.assertEqual(saved["id"], "pilot_primary")
            self.assertIn("created_at", saved)
            self.assertIn("updated_at", saved)
            self.assertEqual(storage.get_layout("pilot_primary"), saved)
            self.assertEqual(storage.list_layouts(), [saved])

            updated = storage.save_layout("pilot_primary", {"name": "Pilot Updated"})
            self.assertEqual(updated["created_at"], saved["created_at"])
            self.assertIn("updated_at", updated)
            self.assertEqual(storage.get_layout("pilot_primary")["name"], "Pilot Updated")
            self.assertTrue(storage.delete_layout("pilot_primary"))
            self.assertIsNone(storage.get_layout("pilot_primary"))
            self.assertFalse(storage.delete_layout("pilot_primary"))

    def test_report_metadata_lists_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = FileBackedStorage(tmp)
            storage.save_report_metadata(
                "packet_old",
                {
                    "title": "Old",
                    "run_id": "run_alpha",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            )
            storage.save_report_metadata(
                "packet_new",
                {
                    "title": "New",
                    "run_id": "run_beta",
                    "created_at": "2026-01-02T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                },
            )

            self.assertEqual(
                [record["id"] for record in storage.list_report_metadata()],
                ["packet_new", "packet_old"],
            )

    def test_draft_metadata_helpers_stamp_and_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = FileBackedStorage(tmp)

            saved = storage.save_draft_metadata(
                "approach_draft",
                {"title": "Approach Draft", "scenario_name": "approach", "tags": ["demo"]},
            )

            self.assertEqual(saved["id"], "approach_draft")
            self.assertIn("created_at", saved)
            self.assertIn("updated_at", saved)
            self.assertEqual(storage.list_draft_metadata(), [saved])

    def test_public_helpers_reject_traversal_and_non_json_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = FileBackedStorage(root)

            with self.assertRaises(ValueError):
                storage.save_layout("../escape", {"name": "bad"})
            with self.assertRaises(ValueError):
                storage.save_report_metadata("bad_report", {"score": float("nan")})
            with self.assertRaises(ValueError):
                storage.save_draft_metadata("bad_draft", {1: "numeric key"})

            self.assertFalse((root.parent / "escape.json").exists())
            self.assertEqual(storage.list_layouts(), [])
            self.assertEqual(storage.list_report_metadata(), [])
            self.assertEqual(storage.list_draft_metadata(), [])


if __name__ == "__main__":
    unittest.main()
