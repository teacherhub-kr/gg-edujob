import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


requests = types.ModuleType("requests")


class ConnectTimeout(Exception):
    pass


class ReadTimeout(Exception):
    pass


requests.ConnectTimeout = ConnectTimeout
requests.ReadTimeout = ReadTimeout
requests.Session = object
sys.modules.setdefault("requests", requests)

bs4 = types.ModuleType("bs4")
bs4.BeautifulSoup = object
sys.modules.setdefault("bs4", bs4)


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "crawl_cleaneye_foundation_jobs.py"
SPEC = importlib.util.spec_from_file_location("cleaneye_collector", MODULE_PATH)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class Response:
    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class CleanEyeBootstrapRetryTests(unittest.TestCase):
    @patch.object(collector.time, "sleep")
    def test_retries_one_connect_timeout_then_succeeds(self, sleep):
        session = FakeSession([requests.ConnectTimeout("first"), Response()])

        collector.bootstrap(session)

        self.assertEqual(len(session.calls), 2)
        self.assertEqual(
            session.calls[0][1]["timeout"],
            (
                collector.BOOTSTRAP_CONNECT_TIMEOUT_SECONDS,
                collector.BOOTSTRAP_READ_TIMEOUT_SECONDS,
            ),
        )
        sleep.assert_called_once_with(collector.BOOTSTRAP_RETRY_BACKOFF_SECONDS)

    @patch.object(collector.time, "sleep")
    def test_exhaustion_remains_fail_closed(self, sleep):
        session = FakeSession(
            [requests.ConnectTimeout("first"), requests.ConnectTimeout("second")]
        )

        with self.assertRaises(requests.ConnectTimeout):
            collector.bootstrap(session)

        self.assertEqual(len(session.calls), collector.BOOTSTRAP_ATTEMPTS)
        sleep.assert_called_once_with(collector.BOOTSTRAP_RETRY_BACKOFF_SECONDS)

    @patch.object(collector.time, "sleep")
    def test_non_connect_failures_are_not_retried(self, sleep):
        session = FakeSession([requests.ReadTimeout("read")])

        with self.assertRaises(requests.ReadTimeout):
            collector.bootstrap(session)

        self.assertEqual(len(session.calls), 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
