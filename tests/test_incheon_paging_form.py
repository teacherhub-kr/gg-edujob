import unittest
from unittest.mock import patch

from scripts import merge_incheon_official as ice


class Response:
    def __init__(self, text, url=ice.LIST_URL, content=None):
        self.text = text
        self.url = url
        self.content = content if content is not None else text.encode("utf-8")
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"
        self.status_code = 200
        self.headers = {"content-type": "text/html"}

    def raise_for_status(self):
        return None


def paging_form(csrf="token-for-test", action="/ice/na/ntt/selectNttList.do"):
    return f"""
    <html><body>
      <form name="pagingForm" method="post" action="{action}">
        <input type="hidden" name="currPage" value="1">
        <input type="hidden" name="listUseAt" value="Y">
        <input type="hidden" name="bbsId" value="1981">
        <input type="hidden" name="mi" value="10997">
        <input type="hidden" name="CSRFToken" value="{csrf}">
      </form>
    </body></html>
    """


class IncheonPagingFormTests(unittest.TestCase):
    def test_posts_complete_official_form_with_session_csrf(self):
        first = Response(paging_form())
        second = Response("<html>page two</html>")

        with patch.object(ice.SESSION, "post", return_value=second) as post:
            actual = ice.fetch_paging_form(first, 2, ice.REQUIRED_BOARDS[0])

        self.assertIs(actual, second)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://www.ice.go.kr/ice/na/ntt/selectNttList.do")
        fields = dict(kwargs["data"])
        self.assertEqual(fields["currPage"], "2")
        self.assertEqual(fields["bbsId"], "1981")
        self.assertEqual(fields["mi"], "10997")
        self.assertEqual(fields["CSRFToken"], "token-for-test")
        self.assertEqual(kwargs["headers"]["Origin"], "https://www.ice.go.kr")
        self.assertEqual(kwargs["headers"]["Referer"], ice.LIST_URL)

    def test_unique_document_csrf_is_bound_to_paging_form(self):
        token = "123e4567-e89b-12d3-a456-426614174000"
        html = paging_form(csrf="").replace(
            "</body>", f'<input type="hidden" name="CSRFToken" value="{token}"></body>'
        )
        first = Response(html)
        second = Response("<html>page two</html>")

        with patch.object(ice.SESSION, "post", return_value=second) as post:
            ice.fetch_paging_form(first, 2, ice.REQUIRED_BOARDS[0])

        fields = dict(post.call_args.kwargs["data"])
        self.assertEqual(fields["CSRFToken"], token)

    def test_unique_injector_script_csrf_is_bound_to_paging_form(self):
        token = "123e4567-e89b-12d3-a456-426614174000"
        script = (
            "<script>document.forms.pagingForm.insertAdjacentHTML("
            "'beforeend','<input type=hidden name=CSRFToken value=\"" + token + "\">'"
            ");</script>"
        )
        first = Response(paging_form(csrf="").replace("</body>", script + "</body>"))
        second = Response("<html>page two</html>")

        with patch.object(ice.SESSION, "post", return_value=second) as post:
            ice.fetch_paging_form(first, 2, ice.REQUIRED_BOARDS[0])

        fields = dict(post.call_args.kwargs["data"])
        self.assertEqual(fields["CSRFToken"], token)

    def test_unique_unlabelled_document_uuid_is_bound_to_paging_form(self):
        token = "123e4567-e89b-12d3-a456-426614174000"
        first = Response(
            paging_form(csrf="").replace(
                "</body>", f"<script>window.__runtime = '{token}'</script></body>"
            )
        )
        second = Response("<html>page two</html>")

        with patch.object(ice.SESSION, "post", return_value=second) as post:
            ice.fetch_paging_form(first, 2, ice.REQUIRED_BOARDS[0])

        fields = dict(post.call_args.kwargs["data"])
        self.assertEqual(fields["CSRFToken"], token)

    def test_ambiguous_unlabelled_document_uuids_fail_before_network(self):
        first_token = "123e4567-e89b-12d3-a456-426614174000"
        second_token = "123e4567-e89b-12d3-a456-426614174001"
        html = paging_form(csrf="").replace(
            "</body>",
            f"<script>window.__a = '{first_token}'; window.__b = '{second_token}'</script></body>",
        )
        first = Response(html)

        with patch.object(ice.SESSION, "post") as post:
            with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                ice.fetch_paging_form(first, 2, ice.REQUIRED_BOARDS[0])
        post.assert_not_called()

    def test_ambiguous_injector_tokens_fail_before_network(self):
        first_token = "123e4567-e89b-12d3-a456-426614174000"
        second_token = "123e4567-e89b-12d3-a456-426614174001"
        script = f"<script>CSRFToken {first_token} CSRFToken {second_token}</script>"
        first = Response(paging_form(csrf="").replace("</body>", script + "</body>"))

        with patch.object(ice.SESSION, "post") as post:
            with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                ice.fetch_paging_form(first, 2, ice.REQUIRED_BOARDS[0])
        post.assert_not_called()

    def test_missing_csrf_fails_before_network(self):
        first = Response(paging_form(csrf=""))
        with patch.object(ice.SESSION, "post") as post:
            with self.assertRaisesRegex(ValueError, "CSRF token missing"):
                ice.fetch_paging_form(first, 2, ice.REQUIRED_BOARDS[0])
        post.assert_not_called()

    def test_cross_host_form_action_fails_before_network(self):
        first = Response(paging_form(action="https://example.test/steal"))
        with patch.object(ice.SESSION, "post") as post:
            with self.assertRaisesRegex(ValueError, "host is not allowlisted"):
                ice.fetch_paging_form(first, 2, ice.REQUIRED_BOARDS[0])
        post.assert_not_called()

    @patch.object(ice.time, "sleep")
    @patch.object(ice, "reset_session")
    @patch.object(ice, "parse_table_rows")
    @patch.object(ice, "fetch_paging_form")
    @patch.object(ice, "fetch_with_one_explicit_retry")
    def test_post_replay_uses_one_bounded_get_and_requires_distinct_ids(
        self, get_page, post_page, parse_rows, reset_session, sleep
    ):
        first = Response(paging_form())
        replay = Response(paging_form())
        distinct = Response("<html>distinct page two</html>", url=ice.with_page(ice.LIST_URL, 2))
        get_page.side_effect = [first, distinct]
        post_page.return_value = replay
        parse_rows.side_effect = [
            ([{"id": "ice-central-1", "registered": "2026/11/08", "applyEnd": ""}],
             {"rawRows": 1, "datedRows": 1, "pageDates": ["2026/11/08"],
              "pageIds": ["1"], "pageText": ""}),
            ([{"id": "ice-central-1", "registered": "2026/11/08", "applyEnd": ""}],
             {"rawRows": 1, "datedRows": 1, "pageDates": ["2026/11/08"],
              "pageIds": ["1"], "pageText": ""}),
            ([{"id": "ice-central-2", "registered": "2026/01/01", "applyEnd": ""}],
             {"rawRows": 1, "datedRows": 1, "pageDates": ["2026/01/01"],
              "pageIds": ["2"], "pageText": ""}),
        ]

        rows, meta = ice.scrape_board(
            ice.REQUIRED_BOARDS[0], lookback_days=90, max_pages=3, check_only=False
        )

        self.assertEqual([row["id"] for row in rows], ["ice-central-1", "ice-central-2"])
        self.assertTrue(meta["coverageComplete"])
        self.assertEqual(meta["stopReason"], "lookback-exhausted")
        self.assertEqual(get_page.call_count, 2)
        reset_session.assert_called_once_with()
        self.assertTrue(meta["pageResponseEvidence"][1]["getFallback"]["success"])
        post_page.assert_called_once_with(first, 2, ice.REQUIRED_BOARDS[0])

    @patch.object(ice.time, "sleep")
    @patch.object(ice, "reset_session")
    @patch.object(ice, "parse_table_rows")
    @patch.object(ice, "fetch_paging_form")
    @patch.object(ice, "fetch_with_one_explicit_retry")
    def test_nonadjacent_replay_uses_fresh_get_and_requires_globally_distinct_ids(
        self, get_page, post_page, parse_rows, reset_session, sleep
    ):
        first = Response(paging_form())
        second = Response(paging_form())
        replay_first = Response(paging_form())
        distinct_third = Response("<html>distinct page three</html>", url=ice.with_page(ice.LIST_URL, 3))
        get_page.side_effect = [first, distinct_third]
        post_page.side_effect = [second, replay_first]
        parse_rows.side_effect = [
            ([{"id": "ice-central-1", "registered": "2026/11/08", "applyEnd": ""}],
             {"rawRows": 1, "datedRows": 1, "pageDates": ["2026/11/08"],
              "pageIds": ["1"], "pageText": ""}),
            ([{"id": "ice-central-2", "registered": "2026/11/07", "applyEnd": ""}],
             {"rawRows": 1, "datedRows": 1, "pageDates": ["2026/11/07"],
              "pageIds": ["2"], "pageText": ""}),
            ([{"id": "ice-central-1", "registered": "2026/11/08", "applyEnd": ""}],
             {"rawRows": 1, "datedRows": 1, "pageDates": ["2026/11/08"],
              "pageIds": ["1"], "pageText": ""}),
            ([{"id": "ice-central-3", "registered": "2026/01/01", "applyEnd": ""}],
             {"rawRows": 1, "datedRows": 1, "pageDates": ["2026/01/01"],
              "pageIds": ["3"], "pageText": ""}),
        ]

        rows, meta = ice.scrape_board(
            ice.REQUIRED_BOARDS[0], lookback_days=90, max_pages=4, check_only=False
        )

        self.assertEqual([row["id"] for row in rows], [
            "ice-central-1", "ice-central-2", "ice-central-3"
        ])
        self.assertTrue(meta["coverageComplete"])
        self.assertEqual(meta["stopReason"], "lookback-exhausted")
        reset_session.assert_called_once_with()
        self.assertTrue(meta["pageResponseEvidence"][2]["getFallback"]["success"])
        self.assertEqual(post_page.call_count, 2)

    @patch.object(ice.time, "sleep")
    @patch.object(ice, "parse_table_rows")
    @patch.object(ice, "fetch_paging_form")
    @patch.object(ice, "fetch_with_one_explicit_retry")
    def test_traversal_uses_get_once_then_form_post(
        self, get_first, post_page, parse_rows, sleep
    ):
        first = Response(paging_form())
        second = Response("<html><body>" + "normal board navigation " * 20 + "</body></html>")
        get_first.return_value = first
        post_page.return_value = second
        parse_rows.side_effect = [
            (
                [{"id": "ice-central-1", "registered": "2026/11/05", "applyEnd": ""}],
                {
                    "rawRows": 1,
                    "datedRows": 1,
                    "pageDates": ["2026/11/05"],
                    "pageIds": ["1"],
                    "pageText": "",
                },
            ),
            (
                [],
                {
                    "rawRows": 0,
                    "datedRows": 0,
                    "pageDates": [],
                    "pageIds": [],
                    "pageText": "",
                },
            ),
        ]

        rows, meta = ice.scrape_board(
            ice.REQUIRED_BOARDS[0], lookback_days=90, max_pages=2, check_only=False
        )

        self.assertEqual([row["id"] for row in rows], ["ice-central-1"])
        self.assertTrue(meta["coverageComplete"])
        self.assertEqual(meta["stopReason"], "empty-page")
        get_first.assert_called_once()
        post_page.assert_called_once_with(first, 2, ice.REQUIRED_BOARDS[0])


if __name__ == "__main__":
    unittest.main()
