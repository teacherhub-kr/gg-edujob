import sys
import unittest

sys.path.insert(0, "scripts")
import source_catalog


class SourceCatalogTests(unittest.TestCase):
    def test_unified_catalog_matches_current_metro_contract(self):
        catalog = source_catalog.build_catalog()
        self.assertEqual(source_catalog.validate_catalog(catalog), [])
        self.assertEqual(catalog["counts"]["officialEducation"], 44)
        self.assertEqual(catalog["counts"]["publicFoundations"], 55)
        self.assertGreaterEqual(catalog["counts"]["publicFoundationsDirect"], 20)

    def test_public_and_private_supplemental_sources_are_not_conflated(self):
        catalog = source_catalog.build_catalog()
        classes = {row["key"]: row["sourceClass"] for row in catalog["supplemental"]}
        self.assertEqual(classes["lessoninfo"], "private-discovery")
        self.assertEqual(classes["jobteacher"], "private-discovery")
        self.assertEqual(classes["artmore"], "private-discovery")
        self.assertEqual(classes["gonggonggangsa"], "private-discovery")
        self.assertEqual(classes["cleaneye"], "public-aggregator")
        self.assertEqual(classes["seekle"], "public-institution")
        self.assertEqual(classes["boramyc"], "public-institution")

    def test_onboarding_candidates_are_not_publication_sources_yet(self):
        catalog = source_catalog.build_catalog()
        candidates = {row["key"]: row for row in catalog["onboardingCandidates"]}
        self.assertEqual(set(candidates), {"hunjang", "public-instructor"})
        self.assertTrue(all(row["status"] == "candidate" for row in candidates.values()))


if __name__ == "__main__":
    unittest.main()
