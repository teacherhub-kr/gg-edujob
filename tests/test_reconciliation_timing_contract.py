from pathlib import Path
import unittest


class ReconciliationTimingContractTests(unittest.TestCase):
    def test_seoul_central_is_final_live_network_read(self):
        source = Path("scripts/reconcile_source_ids.py").read_text(encoding="utf-8")
        support_pos = source.index("support_results, _support_rows = incheon_support.crawl_all_support_offices")
        seoul_pos = source.index("se_central = primary.scrape_seoul_central()")
        by_id_pos = source.index("by_id = {}")
        self.assertLess(support_pos, seoul_pos)
        self.assertLess(seoul_pos, by_id_pos)

    def test_generated_at_is_stamped_after_full_crawl(self):
        source = Path("scripts/reconcile_source_ids.py").read_text(encoding="utf-8")
        crawl_pos = source.index("sources, official = crawl_official_ids()")
        generated_pos = source.index('generated_at = datetime.now(KST).strftime')
        dataset_pos = source.index("dataset_ids_before =")
        self.assertLess(crawl_pos, generated_pos)
        self.assertLess(generated_pos, dataset_pos)
        self.assertIn('"generatedAt": generated_at', source)


if __name__ == "__main__":
    unittest.main()
