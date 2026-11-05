from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ice-pagination-contract-probe.yml"
BROWSER_PROBE = ROOT / "scripts/probe_incheon_browser_pagination.cjs"


def test_probe_collects_both_results_before_final_gate():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "scripts/probe_incheon_browser_pagination.cjs" in text
    assert "id: browser_probe" in text
    assert "id: requests_probe" in text
    assert text.count("continue-on-error: true") == 2
    assert "if: always()" in text
    assert "steps.browser_probe.outcome" in text
    assert "steps.requests_probe.outcome" in text
    assert 'BROWSER_OUTCOME}" != "success"' in text
    assert 'REQUESTS_OUTCOME}" != "success"' in text


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


def test_browser_probe_records_only_the_request_contract():
    text = BROWSER_PROBE.read_text(encoding="utf-8")

    assert "page.waitForRequest(candidate=>candidate.isNavigationRequest()" in text
    assert "candidate.frame()===page.mainFrame()" in text
    assert "BROWSER_PAGE2_REQUEST" in text
    assert "method:request.method()" in text
    assert "pathname:requestUrl.pathname" in text
    assert "search:requestUrl.search" in text
    assert "postData:postData?postData.slice(0,2000):null" in text
    assert "request.headers()" not in text
    assert "page.context().cookies()" not in text
