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


class RailwayHeartbeatTests(unittest.TestCase):
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
        now = datetime.now(timezone.utc)
        payload = {
            "workflow_runs": [
                {
                    "status": "in_progress",
                    "created_at": (now - timedelta(minutes=30)).isoformat(),
                    "run_started_at": (now - timedelta(minutes=2)).isoformat(),
                }
            ]
        }
        with patch.dict(
            os.environ,
            {"HEARTBEAT_ENABLED": "true", "GH_DISPATCH_TOKEN": "test-token"},
            clear=True,
        ):
            with patch.object(
                hb,
                "request",
                return_value=(200, json.dumps(payload).encode("utf-8")),
            ) as request:
                self.assertEqual(hb.main(), 0)
                self.assertEqual(request.call_count, 1)

    def test_recent_rerun_uses_run_started_at(self):
        now = datetime.now(timezone.utc)
        payload = {
            "workflow_runs": [
                {
                    "status": "completed",
                    "conclusion": "success",
                    "created_at": (now - timedelta(hours=8)).isoformat(),
                    "run_started_at": (now - timedelta(minutes=5)).isoformat(),
                }
            ]
        }
        with patch.dict(
            os.environ,
            {"HEARTBEAT_ENABLED": "true", "GH_DISPATCH_TOKEN": "test-token"},
            clear=True,
        ):
            with patch.object(
                hb,
                "request",
                return_value=(200, json.dumps(payload).encode("utf-8")),
            ) as request:
                self.assertEqual(hb.main(), 0)
                self.assertEqual(request.call_count, 1)

    def test_stale_watchdog_dispatches_main(self):
        now = datetime.now(timezone.utc)
        payload = {
            "workflow_runs": [
                {
                    "status": "completed",
                    "conclusion": "success",
                    "created_at": (now - timedelta(hours=2)).isoformat(),
                    "run_started_at": (now - timedelta(hours=2)).isoformat(),
                }
            ]
        }
        calls = []

        def fake_request(method, path, token, body=None):
            calls.append((method, path, token, body))
            if method == "GET":
                return 200, json.dumps(payload).encode("utf-8")
            return 204, b""

        with patch.dict(
            os.environ,
            {"HEARTBEAT_ENABLED": "true", "GH_DISPATCH_TOKEN": "test-token"},
            clear=True,
        ):
            with patch.object(hb, "request", side_effect=fake_request):
                self.assertEqual(hb.main(), 0)

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0], "POST")
        self.assertEqual(
            calls[1][1],
            "/actions/workflows/fast-refresh-watchdog.yml/dispatches",
        )
        self.assertEqual(calls[1][3], {"ref": "main"})


if __name__ == "__main__":
    unittest.main()
