#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import complete_support_coverage as coverage


class CompleteSupportCoverageEntrypointTest(unittest.TestCase):
    def test_traversal_entrypoints_remain_callable(self):
        for name in ("gyeonggi_board", "seoul_board", "production_filter", "main"):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(coverage, name, None)), f"{name} must remain callable")

    def test_production_lookback_contract_remains_90_days(self):
        self.assertEqual(coverage.LOOKBACK_DAYS, 90)


if __name__ == "__main__":
    unittest.main()
