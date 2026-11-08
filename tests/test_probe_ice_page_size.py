import unittest

from scripts.probe_ice_page_size import ids


class IcePageSizeProbeTests(unittest.TestCase):
    def test_extracts_source_native_data_ids(self):
        html = """
        <table>
          <tr><td><a class="nttInfoBtn" data-id="3387699">공고</a></td></tr>
          <tr><td><a class="nttInfoBtn" data-id="3387700">공고</a></td></tr>
        </table>
        """
        self.assertEqual(ids(html), ["3387699", "3387700"])

    def test_ignores_unrelated_numbers(self):
        html = '<span>20261108</span><a class="other" data-id="9999999">기타</a>'
        self.assertEqual(ids(html), [])

    def test_supports_ntt_sn_fallback(self):
        html = "goDetail('bbsId=1981&nttSn=3387699')"
        self.assertEqual(ids(html), ["3387699"])


if __name__ == "__main__":
    unittest.main()
