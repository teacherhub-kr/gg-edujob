import importlib.util
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "railway_heartbeat", ROOT / "ops" / "heartbeat" / "heartbeat.py"
)
hb = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(hb)


def run(minutes_ago, status="completed", *, event="schedule", branch="main"):
    started = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {
        "status": status,
        "event": event,
        "head_branch": branch,
        "created_at": started.isoformat(),
        "run_started_at": started.isoformat(),
    }


class RailwayHeartbeatTests(unittest.TestCase):
    def test_target_exists_and_is_a_guarded_dispatcher(self):
        self.assertEqual(hb.WORKFLOW, "production-operations-watchdog.yml")
        content = (ROOT / ".github" / "workflows" / hb.WORKFLOW).read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", content)
        self.assertIn("scripts/private_refresh_policy.py", content)
        self.assertNotIn("fast-refresh-watchdog.yml", hb.WORKFLOW)

    def test_disabled_never_calls_github(self):
        with patch.dict(os.environ, {"HEARTBEAT_ENABLED": "false"}, clear=True):
            with patch.object(hb, "request") as request:
                self.assertEqual(hb.main(), 0)
                request.assert_not_called()

    def test_missing_token_fails_without_network(self):
        with patch.dict(os.environ, {"HEARTBEAT_ENABLED": "true"}, clear=True):
            with patch.object(hb, "request") as request:
                self.assertEqual(hb.main(), 2)
                request.assert_not_called()

    def test_active_watchdog_skips_dispatch(self):
        payload = {"workflow_runs": [run(30, status="in_progress")]}
        with patch.dict(os.environ, {"HEARTBEAT_ENABLED": "true", "GH_DISPATCH_TOKEN": "test-token"}, clear=True):
            with patch.object(hb, "request", return_value=(200, json.dumps(payload).encode())) as request:
                self.assertEqual(hb.main(), 0)
                self.assertEqual(request.call_count, 1)

    def test_recent_manual_run_skips_dispatch(self):
        payload = {"workflow_runs": [run(5, event="workflow_dispatch"), run(180)]}
        with patch.dict(os.environ, {"HEARTBEAT_ENABLED": "true", "GH_DISPATCH_TOKEN": "test-token"}, clear=True):
            with patch.object(hb, "request", return_value=(200, json.dumps(payload).encode())) as request:
                self.assertEqual(hb.main(), 0)
                self.assertEqual(request.call_count, 1)

    def test_stale_watchdog_dispatches_existing_main_guarded_supervisor(self):
        payload = {"workflow_runs": [run(125)]}
        calls = []
        def fake(method, path, token, body=None):
            calls.append((method, path, body))
            if method == "GET":
                return 200, json.dumps(payload).encode()
            return 204, b""
        with patch.dict(os.environ, {"HEARTBEAT_ENABLED": "true", "GH_DISPATCH_TOKEN": "test-token"}, clear=True):
            with patch.object(hb, "request", side_effect=fake):
                self.assertEqual(hb.main(), 0)
        self.assertEqual([x[0] for x in calls], ["GET", "GET", "POST"])
        self.assertEqual(calls[-1][1], "/actions/workflows/production-operations-watchdog.yml/dispatches")
        self.assertEqual(calls[-1][2], {"ref": "main"})

    def test_new_active_run_on_second_read_prevents_dispatch(self):
        responses = [
            {"workflow_runs": [run(180)]},
            {"workflow_runs": [run(1, status="queued"), run(180)]},
        ]
        calls = []
        def fake(method, path, token, body=None):
            calls.append(method)
            self.assertEqual(method, "GET")
            return 200, json.dumps(responses.pop(0)).encode()
        with patch.dict(os.environ, {"HEARTBEAT_ENABLED": "true", "GH_DISPATCH_TOKEN": "test-token"}, clear=True):
            with patch.object(hb, "request", side_effect=fake):
                self.assertEqual(hb.main(), 0)
        self.assertEqual(calls, ["GET", "GET"])

    def test_empty_history_cannot_dispatch(self):
        with patch.dict(os.environ, {"HEARTBEAT_ENABLED": "true", "GH_DISPATCH_TOKEN": "test-token"}, clear=True):
            with patch.object(hb, "request", return_value=(200, b'{"workflow_runs":[]}')) as request:
                self.assertEqual(hb.main(), 2)
                self.assertEqual(request.call_count, 1)

    def test_other_branch_and_pr_runs_cannot_anchor(self):
        payload = {"workflow_runs": [run(150, branch="test"), run(150, event="pull_request")]}
        with patch.dict(os.environ, {"HEARTBEAT_ENABLED": "true", "GH_DISPATCH_TOKEN": "test-token"}, clear=True):
            with patch.object(hb, "request", return_value=(200, json.dumps(payload).encode())) as request:
                self.assertEqual(hb.main(), 2)
                self.assertEqual(request.call_count, 1)

    def test_malformed_response_cannot_dispatch(self):
        with patch.dict(os.environ, {"HEARTBEAT_ENABLED": "true", "GH_DISPATCH_TOKEN": "test-token"}, clear=True):
            with patch.object(hb, "request", return_value=(200, b'{"wrong":[]}')) as request:
                self.assertEqual(hb.main(), 2)
                self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
