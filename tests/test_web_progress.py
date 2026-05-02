import json
import unittest
from datetime import datetime, timezone

from aerosim6dof.web.progress import (
    ProgressEvent,
    cancel_descriptor,
    is_terminal_phase,
    make_progress_event,
    merge_progress_event,
    normalize_percent,
    normalize_phase,
    progress_from_job_summary,
    retry_descriptor,
)


class WebProgressTests(unittest.TestCase):
    def test_progress_normalization_is_defensive(self):
        self.assertEqual(normalize_phase("In Progress"), "running")
        self.assertEqual(normalize_phase("done"), "completed")
        self.assertEqual(normalize_phase(""), "queued")
        self.assertEqual(normalize_percent(0.42), 42.0)
        self.assertEqual(normalize_percent(42), 42.0)
        self.assertEqual(normalize_percent(150), 100.0)
        self.assertEqual(normalize_percent(float("nan")), 0.0)
        self.assertEqual(normalize_percent(0.5, phase="completed"), 100.0)

        event = make_progress_event(
            "job-1",
            "run",
            phase="active",
            percent=0.25,
            message="running",
            artifact={"bad": float("inf"), "nested": {"ok": True}},
            cancellable=True,
        )
        self.assertEqual(event.phase, "running")
        self.assertEqual(event.percent, 25.0)
        self.assertIsNone(event.artifact["bad"])
        json.dumps(event.to_dict())

    def test_lifecycle_merging_preserves_created_at_and_updates_terminal_state(self):
        created = "2026-05-02T10:00:00Z"
        queued = make_progress_event("job-2", "trim", "queued", 0, "queued", created_at=created)
        running = merge_progress_event(
            queued,
            {"phase": "running", "percent": 0.55, "message": "solving", "cancellable": True},
            updated_at="2026-05-02T10:00:05Z",
        )
        self.assertEqual(running.created_at, created)
        self.assertEqual(running.updated_at, "2026-05-02T10:00:05Z")
        self.assertEqual(running.phase, "running")
        self.assertEqual(running.percent, 55.0)
        self.assertTrue(running.cancellable)

        completed = merge_progress_event(running, {"phase": "success", "message": "complete"})
        self.assertEqual(completed.phase, "completed")
        self.assertEqual(completed.percent, 100.0)
        self.assertFalse(completed.cancellable)

    def test_terminal_detection_accepts_common_aliases(self):
        self.assertTrue(is_terminal_phase("completed"))
        self.assertTrue(is_terminal_phase("FAILED"))
        self.assertTrue(is_terminal_phase("canceled"))
        self.assertTrue(is_terminal_phase("done"))
        self.assertFalse(is_terminal_phase("queued"))
        self.assertFalse(is_terminal_phase("running"))

    def test_cancel_and_retry_descriptors(self):
        running = ProgressEvent(
            job_id="job-3",
            action="monte_carlo",
            phase="running",
            percent=10,
            message="sampling",
            cancellable=True,
            created_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
            updated_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
        )
        self.assertEqual(
            cancel_descriptor(running),
            {
                "job_id": "job-3",
                "method": "POST",
                "path": "/api/jobs/job-3/cancel",
                "enabled": True,
                "phase": "running",
            },
        )
        self.assertFalse(retry_descriptor(running)["enabled"])

        failed = merge_progress_event(running, {"phase": "failed", "message": "bad input"})
        self.assertFalse(cancel_descriptor(failed)["enabled"])
        retry = retry_descriptor(failed)
        self.assertTrue(retry["enabled"])
        self.assertEqual(retry["path"], "/api/jobs/monte_carlo")

    def test_existing_job_summary_adapts_to_progress_event(self):
        event = progress_from_job_summary(
            {
                "id": "abc",
                "action": "inspect_vehicle",
                "status": "completed",
                "message": "completed",
                "progress": 1.0,
                "created_at_utc": "2026-05-02T10:00:00Z",
                "started_at_utc": "2026-05-02T10:00:01Z",
                "finished_at_utc": "2026-05-02T10:00:02Z",
                "events": [{"time_utc": "2026-05-02T10:00:02Z", "status": "completed", "message": "completed", "progress": 1.0}],
                "result": {
                    "output_id": "web_runs~demo",
                    "artifacts": [{"name": "summary.json", "url": "/api/artifacts/web_runs~demo/summary.json"}],
                },
            }
        )
        self.assertEqual(event.job_id, "abc")
        self.assertEqual(event.phase, "completed")
        self.assertEqual(event.percent, 100.0)
        self.assertEqual(event.run_id, "web_runs~demo")
        self.assertEqual(event.artifact["name"], "summary.json")
        self.assertEqual(event.updated_at, "2026-05-02T10:00:02Z")


if __name__ == "__main__":
    unittest.main()
