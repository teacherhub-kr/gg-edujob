import unittest
from unittest.mock import patch

from scripts import merge_incheon_official as ice


def meta_for(count=0, stop_reason="empty-page", access_error=""):
    health = [
        {
            "bbsId": "1981",
            "count": count,
            "stopReason": stop_reason,
            "accessError": access_error,
            "coverageComplete": count > 0,
        },
        {
            "bbsId": "1534",
            "count": count,
            "stopReason": stop_reason,
            "accessError": access_error,
            "coverageComplete": count > 0,
        },
    ]
    return {
        "boardHealth": health,
        "accessError": access_error,
        "paginationRepeated": False,
        "coverageComplete": count > 0,
        "stopReason": "all-required-boards-complete" if count > 0 else "incomplete-required-board",
    }


class IncheonTransientRetryTests(unittest.TestCase):
    def test_all_empty_signature_is_retryable(self):
        self.assertTrue(ice.is_transient_all_empty(meta_for(), []))

    def test_access_error_and_nonempty_are_not_retryable(self):
        self.assertFalse(ice.is_transient_all_empty(meta_for(access_error="timeout"), []))
        self.assertFalse(ice.is_transient_all_empty(meta_for(count=1), [{"id": "x"}]))

    @patch.object(ice, "reset_session")
    @patch.object(ice.time, "sleep")
    @patch.object(ice, "scrape_incheon_central")
    def test_check_only_retries_empty_then_accepts_success(self, scrape, sleep, reset):
        scrape.side_effect = [
            ([], meta_for()),
            ([{"id": "ok"}], meta_for(count=1)),
        ]
        rows, meta = ice.scrape_incheon_with_transient_retry(
            lookback_days=90,
            max_pages=1000,
            check_only=True,
            transient_retries=2,
            retry_delay_seconds=15,
        )
        self.assertEqual(rows, [{"id": "ok"}])
        self.assertTrue(meta["coverageComplete"])
        self.assertEqual(scrape.call_count, 2)
        sleep.assert_called_once_with(15.0)
        reset.assert_called_once_with()

    @patch.object(ice, "reset_session")
    @patch.object(ice.time, "sleep")
    @patch.object(ice, "scrape_incheon_central")
    def test_non_check_only_retries_all_empty_with_fresh_session(self, scrape, sleep, reset):
        scrape.side_effect = [
            ([], meta_for()),
            ([{"id": "ok"}], meta_for(count=1)),
        ]
        rows, meta = ice.scrape_incheon_with_transient_retry(
            lookback_days=90,
            max_pages=1000,
            check_only=False,
            transient_retries=2,
            retry_delay_seconds=15,
        )
        self.assertEqual(rows, [{"id": "ok"}])
        self.assertTrue(meta["coverageComplete"])
        self.assertEqual(scrape.call_count, 2)
        sleep.assert_called_once_with(15.0)
        reset.assert_called_once_with()

    @patch.object(ice, "reset_session")
    @patch.object(ice.time, "sleep")
    @patch.object(ice, "scrape_incheon_central")
    def test_exhausted_all_empty_retries_stay_failed(self, scrape, sleep, reset):
        scrape.return_value = ([], meta_for())
        rows, meta = ice.scrape_incheon_with_transient_retry(
            lookback_days=90,
            max_pages=1000,
            check_only=False,
            transient_retries=2,
            retry_delay_seconds=15,
        )
        self.assertEqual(rows, [])
        self.assertFalse(meta["coverageComplete"])
        self.assertEqual(scrape.call_count, 3)
        self.assertEqual(reset.call_count, 2)
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
