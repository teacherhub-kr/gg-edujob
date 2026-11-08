from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ice-pagination-contract-probe.yml"
BROWSER_PROBE = ROOT / "scripts/probe_incheon_browser_pagination.cjs"


def test_probe_collects_both_results_before_final_gate():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "scripts/probe_incheon_browser_pagination.cjs" in text
    assert "id: production_probe" in text
    assert "id: browser_probe" in text
    assert "id: requests_probe" in text
    assert text.count("continue-on-error: true") == 3
    assert "if: always()" in text
    assert "steps.production_probe.outcome" in text
    assert "steps.browser_probe.outcome" in text
    assert "steps.requests_probe.outcome" in text
    assert 'PRODUCTION_OUTCOME}" != "success"' in text
    assert 'BROWSER_OUTCOME}" != "success"' in text
    assert 'REQUESTS_OUTCOME}" != "success"' in text



def test_production_probe_has_bounded_but_nontrivial_coverage():
    text = WORKFLOW.read_text(encoding="utf-8")
    import re
    match = re.search(r"--lookback-days\s+14\s+--max-pages\s+(\d+)", text)
    assert match, "production probe must specify a page cap for 14-day lookback"
    assert int(match.group(1)) >= 60, "three-page probes cannot prove 14-day coverage"
    assert "timeout-minutes: 25" in text


def test_browser_probe_waits_for_the_page_two_navigation():
    text = BROWSER_PROBE.read_text(encoding="utf-8")

    assert "page.waitForNavigation({waitUntil:'domcontentloaded',timeout:20000})" in text
    assert "page.waitForLoadState('domcontentloaded').catch(()=>{})" not in text


def test_browser_probe_retries_only_bounded_navigation_races():
    text = BROWSER_PROBE.read_text(encoding="utf-8")

    assert "attempt<=3" in text
    assert "execution context was destroyed|navigation" in text
    assert "if(!navigationRace||attempt===3)throw error" in text
    assert "BROWSER_NAVIGATION_RACE_RETRY" in text


def test_browser_probe_redacts_request_secrets():
    text = BROWSER_PROBE.read_text(encoding="utf-8")

    assert "page.waitForRequest(candidate=>candidate.isNavigationRequest()" in text
    assert "candidate.frame()===page.mainFrame()" in text
    assert "BROWSER_PAGE2_REQUEST" in text
    assert "method:request.method()" in text
    assert "pathname:requestUrl.pathname" in text
    assert "search:requestUrl.search" in text
    assert "fieldNames" in text
    assert "currPage:postParams.get('currPage')" in text
    assert "bbsId:postParams.get('bbsId')" in text
    assert "mi:postParams.get('mi')" in text
    assert "csrfTokenPresent:postParams.has('CSRFToken')" in text
    assert "postData:" not in text
    assert "request.headers()" not in text
    assert "postParams.get('CSRFToken')" not in text
    assert "BROWSER_CSRF_LOCATION" in text
    assert "cookie=>cookie.name" in text
    assert "cookie=>cookie.value" not in text


if __name__ == "__main__":
    test_probe_collects_both_results_before_final_gate()
    test_production_probe_has_bounded_but_nontrivial_coverage()
    test_browser_probe_waits_for_the_page_two_navigation()
    test_browser_probe_retries_only_bounded_navigation_races()
    test_browser_probe_redacts_request_secrets()
    print("ICE probe regression contracts passed")
