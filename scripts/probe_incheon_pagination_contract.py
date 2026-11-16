#!/usr/bin/env python3
"""Read-only diagnostic for ICE central page-2 contract; never publishes listings."""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from merge_incheon_official import (
    REQUIRED_BOARDS, SESSION, build_session, extract_document_csrf,
    fetch_with_one_explicit_retry, parse_table_rows, with_page,
)

BOARD = next(board for board in REQUIRED_BOARDS if board["key"] == "central")


def get_url(param: str, page: int) -> str:
    url = urlparse(BOARD["url"])
    qs = parse_qs(url.query, keep_blank_values=True)
    qs[param] = [str(page)]
    return urlunparse((url.scheme, url.netloc, url.path, url.params, urlencode(qs, doseq=True), url.fragment))


def classify(name: str, response, baseline_ids: set[str]) -> dict:
    rows, meta = parse_table_rows(response.text, response.url, 90, BOARD)
    ids = [str(x) for x in meta["pageIds"]]
    observed = re.search(r"페이지\s*(\d+)\s*/\s*(\d+)", meta.get("pageText", ""))
    return {
        "candidate": name, "http": response.status_code,
        "rawRows": meta["rawRows"], "pageIndicator": observed.group(1) if observed else None,
        "firstTwoIds": ids[:2],
        "distinctFromPageOne": bool(ids) and not set(ids).intersection(baseline_ids),
        "sameAsPageOne": bool(ids) and set(ids) == baseline_ids,
        "finalHost": urlparse(response.url).hostname,
    }


def main():
    results = []
    first = fetch_with_one_explicit_retry(with_page(BOARD["url"], 1))
    base_ids = set(parse_table_rows(first.text, first.url, 90, BOARD)[1]["pageIds"])
    if not base_ids:
        # The official CMS sometimes responds with a tiny 200 body; bootstrap
        # once using the same session. This is diagnostic only, not completeness proof.
        try:
            SESSION.get(BOARD["bootstrapUrl"], timeout=(8, 25), allow_redirects=True)
            first = fetch_with_one_explicit_retry(with_page(BOARD["url"], 1))
            base_ids = set(parse_table_rows(first.text, first.url, 90, BOARD)[1]["pageIds"])
        except Exception as exc:
            print("BOOTSTRAP_ERROR", type(exc).__name__, flush=True)
    if not base_ids:
        raise SystemExit("FAIL CLOSED: ICE central page 1 has no parseable official IDs")
    print("BASELINE", json.dumps({"rawIds": len(base_ids), "firstTwoIds": sorted(base_ids)[:2]}, ensure_ascii=False), flush=True)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(first.text, "html.parser")
    uuid_pattern = re.compile(
        r"(?<![0-9a-f])([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})(?![0-9a-f])",
        re.IGNORECASE,
    )
    raw_uuids = set(uuid_pattern.findall(first.text))
    print("CSRF_RAW_SHAPE", json.dumps({
        "csrfMentions": len(re.findall(r"CSRFToken", first.text, re.IGNORECASE)),
        "uniqueUuidCount": len(raw_uuids),
        "namedInputCount": len(soup.find_all("input", attrs={"name": "CSRFToken"})),
    }, ensure_ascii=False), flush=True)
    page_controls = []
    for a in soup.find_all(["a", "button"]):
        label = a.get_text(" ", strip=True)
        if label in {"2", "3", "다음", "마지막", "맨마지막"} or "page" in str(a.get("class") or "").lower():
            page_controls.append({
                "label": label[:22], "href": str(a.get("href") or "")[:180],
                "onclick": str(a.get("onclick") or "")[:180],
                "data": {k:str(v)[:100] for k,v in a.attrs.items() if k.startswith("data-")}
            })
    forms = []
    for form in soup.find_all("form"):
        fields = [i.get("name") for i in form.find_all(["input","select"]) if i.get("name")]
        forms.append({"id":form.get("id"),"name":form.get("name"),
                      "method":form.get("method"),"action":form.get("action"),
                      "fields":fields[:80]})
    js_hints = []
    for js in soup.find_all("script"):
        content = js.string or js.get_text() or ""
        for line in content.splitlines():
            if re.search(r"currPage|pageIndex|fn.*[Pp]age|go.*[Pp]age|move.*[Pp]age|pageNum|pagination", line):
                js_hints.append(line.strip()[:250])
    print("PAGE_CONTROLS", json.dumps(page_controls[:26], ensure_ascii=False), flush=True)
    print("FORM_FIELDS", json.dumps(forms[:15], ensure_ascii=False), flush=True)
    print("PAGINATION_JS_HINTS", json.dumps(js_hints[:30], ensure_ascii=False), flush=True)
    # Reproduce the actual first-party goPaging(2) JavaScript form submission.
    from urllib.parse import urljoin
    paging = soup.find("form", attrs={"name": "pagingForm"})
    if paging is not None:
        fields = []
        for element in paging.find_all("input"):
            name = element.get("name")
            if not name or str(element.get("type") or "").lower() in {"submit", "button", "image"}:
                continue
            fields.append((name, "2" if name == "currPage" else str(element.get("value") or "")))
        if not any(name == "CSRFToken" and value for name, value in fields):
            token = extract_document_csrf(soup)
            if token:
                fields.append(("CSRFToken", token))
        target = urljoin(first.url, str(paging.get("action") or ""))
        if urlparse(target).hostname != "www.ice.go.kr":
            raise SystemExit("FAIL: unexpected ICE pagination form host")
        try:
            response = SESSION.post(
                target, data=fields, headers={"Referer": first.url},
                timeout=(8, 25), allow_redirects=True,
            )
            response.raise_for_status()
            report = classify("POST official-pagingForm", response, base_ids)
        except Exception as exc:
            report = {"candidate": "POST official-pagingForm", "errorType": type(exc).__name__}
        results.append(report)
        print("PROBE", json.dumps(report, ensure_ascii=False), flush=True)

        # Some ICE edge responses ignore a body-only currPage on the bare form
        # action even though the browser submitted the official form. Probe the
        # same allowlisted list endpoint with its canonical board query retained,
        # then with currPage duplicated in the query. These are read-only list
        # requests; a candidate is useful only if real official IDs are distinct.
        query_targets = (
            ("POST official-pagingForm action+board-query", BOARD["url"]),
            ("POST official-pagingForm action+page-query", get_url("currPage", 2)),
        )
        for candidate, query_target in query_targets:
            try:
                response = SESSION.post(
                    query_target, data=fields, headers={"Referer": first.url},
                    timeout=(8, 25), allow_redirects=True,
                )
                response.raise_for_status()
                query_report = classify(candidate, response, base_ids)
            except Exception as exc:
                query_report = {"candidate": candidate, "errorType": type(exc).__name__}
            results.append(query_report)
            print("PROBE", json.dumps(query_report, ensure_ascii=False), flush=True)
    # The first-party host aliases are already documented by the production
    # collector. Check whether their live CMS honors its own posted pagingForm.
    from merge_incheon_official import OFFICIAL_FETCH_ALIASES, with_host
    for alias in OFFICIAL_FETCH_ALIASES:
        try:
            alias_url = with_host(BOARD["url"], alias)
            response_one = SESSION.get(alias_url, timeout=(8, 25), allow_redirects=True)
            response_one.raise_for_status()
            alias_base = set(parse_table_rows(response_one.text, response_one.url, 90, BOARD)[1]["pageIds"])
            alias_soup = BeautifulSoup(response_one.text, "html.parser")
            paging_form = alias_soup.find("form", attrs={"name": "pagingForm"})
            if not alias_base or paging_form is None:
                print("ALIAS", json.dumps({"host":alias,"pageOneIds":len(alias_base),
                      "hasPagingForm":paging_form is not None}), flush=True)
                continue
            fields = [(item.get("name"), "2" if item.get("name") == "currPage" else str(item.get("value") or ""))
                      for item in paging_form.find_all("input") if item.get("name")]
            target = urljoin(response_one.url, str(paging_form.get("action") or ""))
            if urlparse(target).hostname != alias:
                raise ValueError("unexpected alias pagingForm target")
            response_two = SESSION.post(target, data=fields, headers={"Referer": response_one.url},
                                        timeout=(8, 25), allow_redirects=True)
            response_two.raise_for_status()
            report = classify("POST official-pagingForm alias "+alias, response_two, alias_base)
            results.append(report)
            print("ALIAS", json.dumps(report, ensure_ascii=False), flush=True)
        except Exception as exc:
            print("ALIAS", json.dumps({"host":alias,"errorType":type(exc).__name__}),flush=True)
    for parameter in ("currPage", "pageIndex", "pageNo", "currentPage", "page"):
        try:
            response = fetch_with_one_explicit_retry(get_url(parameter, 2))
            report = classify("GET "+parameter, response, base_ids)
        except Exception as exc:
            report = {"candidate": "GET "+parameter, "errorType": type(exc).__name__}
        results.append(report)
        print("PROBE", json.dumps(report, ensure_ascii=False), flush=True)
    for parameter in ("currPage", "pageIndex"):
        try:
            response = SESSION.post(
                BOARD["url"],
                data={"bbsId": BOARD["bbsId"], "mi": BOARD["mi"], parameter: "2"},
                headers={"Referer": BOARD["url"]},
                timeout=(8, 25), allow_redirects=True,
            )
            response.raise_for_status()
            report = classify("POST "+parameter, response, base_ids)
        except Exception as exc:
            report = {"candidate": "POST "+parameter, "errorType": type(exc).__name__}
        results.append(report)
        print("PROBE", json.dumps(report, ensure_ascii=False), flush=True)
    valid = [x for x in results if x.get("distinctFromPageOne") and x.get("rawRows", 0) > 0]
    print("VALID_PAGE_TWO", json.dumps([x["candidate"] for x in valid], ensure_ascii=False), flush=True)
    if not valid:
        raise SystemExit("FAIL CLOSED: no independently distinct, parseable second page")


if __name__ == "__main__":
    main()
