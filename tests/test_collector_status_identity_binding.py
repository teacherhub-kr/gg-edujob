import sys
import unittest

sys.path.insert(0, "scripts")
import update_collector_status as status


class CollectorStatusIdentityBindingTests(unittest.TestCase):
    def test_current_stable_ids_includes_merged_source_identities(self):
        payload = {
            "jobs": [
                {
                    "province": "경기",
                    "sourceType": "교육지원청 개별 게시판",
                    "url": "https://example.test/detail/100",
                    "sourceIdentities": [
                        "gyeonggi-support:office-a:100",
                        "gyeonggi-support:office-b:200",
                    ],
                }
            ]
        }
        ids = status.current_stable_ids(payload)
        self.assertIn("gyeonggi-support:office-a:100", ids)
        self.assertIn("gyeonggi-support:office-b:200", ids)

    def test_current_stable_ids_ignores_blank_extra_identities(self):
        payload = {"jobs": [{"sourceIdentities": ["", "   ", None]}]}
        ids = status.current_stable_ids(payload)
        self.assertNotIn("", ids)
        self.assertNotIn("   ", ids)


if __name__ == "__main__":
    unittest.main()
