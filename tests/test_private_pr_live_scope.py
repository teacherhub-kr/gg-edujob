import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pr_source_live_scope import requires_live_probe, SOURCE_SPECIFIC_PATHS


class PRSourceLiveScopeTests(unittest.TestCase):
    def test_known_source_parser_edit_must_force_live_proof(self):
        for source, files in SOURCE_SPECIFIC_PATHS.items():
            own_crawler = next(f for f in files if f.startswith("scripts/crawl_"))
            with self.subTest(source=source):
                self.assertTrue(requires_live_probe(source, [own_crawler]))

    def test_changed_exact_post_url_contract_must_force_both_sources_live(self):
        for source in SOURCE_SPECIFIC_PATHS:
            self.assertTrue(requires_live_probe(source, ["scripts/direct_post_links.py"]))

    def test_changed_source_data_or_fixture_must_force_live_proof(self):
        for source, files in SOURCE_SPECIFIC_PATHS.items():
            for path in files:
                if path.startswith("tests/fixtures/") or path.endswith("_jobs.json"):
                    with self.subTest(source=source, path=path):
                        self.assertTrue(requires_live_probe(source, [path]))

    def test_shared_projection_alone_is_tested_by_unified_not_external_network(self):
        for source in SOURCE_SPECIFIC_PATHS:
            self.assertFalse(requires_live_probe(source, [
                "scripts/build_unified_search_multi.py",
                "scripts/build_unified_search.py",
                "scripts/private_source_registry.py",
                "scripts/validate_unified_search_multi.py",
                "tests/test_recruitment_expiry.py",
            ]))

    def test_workflow_only_change_is_not_an_excuse_to_hide_parser_changes(self):
        for source in SOURCE_SPECIFIC_PATHS:
            self.assertFalse(requires_live_probe(source, [
                f".github/workflows/update-{source}-instructor-jobs.yml",
                "scripts/pr_source_live_scope.py",
            ]))
            own_crawler = next(f for f in SOURCE_SPECIFIC_PATHS[source] if f.startswith("scripts/crawl_"))
            self.assertTrue(requires_live_probe(source, [
                f".github/workflows/update-{source}-instructor-jobs.yml",
                own_crawler,
            ]))

    def test_unknown_source_is_fail_closed(self):
        with self.assertRaises(ValueError):
            requires_live_probe("unknown", [])


if __name__ == "__main__":
    unittest.main()
