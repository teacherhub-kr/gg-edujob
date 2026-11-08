#!/usr/bin/env python3
"""Read-only ICE page-size probe. Never asserts complete coverage or writes jobs."""
import argparse
import hashlib
import json
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.ice.go.kr"
PATH = "/ice/na/ntt/selectNttList.do"
PARAMS = {"bbsId": "1981", "mi": "10997"}
ID_PATTERN = re.compile(r"nttSn\s*[=:,'\"() ]+\s*(\d{4,})", re.I)


def ids(html):
    """Extract only source-native posting IDs from the rendered board response."""
    soup = BeautifulSoup(html, "html.parser")
    values = {
        str(anchor.get("data-id"))
        for anchor in soup.select("a.nttInfoBtn[data-id]")
        if str(anchor.get("data-id") or "").isdigit()
    }
    values.update(ID_PATTERN.findall(html))
    return sorted(values)


def probe(session, size):
    url = urljoin(BASE, PATH)
    first = session.get(url, params=PARAMS, timeout=(8, 25))
    first.raise_for_status()
    default_ids = ids(first.text)
    if not default_ids:
        raise RuntimeError("ICE page-size probe found no source-native IDs on page 1")

    soup = BeautifulSoup(first.text, "html.parser")
    form = soup.select_one('form[name="pagingForm"]')
    fields = {}
    if form:
        for inp in form.select("input[name]"):
            fields[inp.get("name")] = inp.get("value", "")
    action = urljoin(first.url, form.get("action") or PATH) if form else url
    method = (form.get("method") or "GET").upper() if form else "GET"
    fields.update(PARAMS)
    fields.update({"currPage": "1", "pageUnit": str(size)})
    response = (
        session.post(action, data=fields, timeout=(8, 25))
        if method == "POST"
        else session.get(action, params=fields, timeout=(8, 25))
    )
    response.raise_for_status()
    response_ids = ids(response.text)
    return {
        "requestedPageUnit": size,
        "status": response.status_code,
        "responseBytes": len(response.content),
        "idsCount": len(response_ids),
        "idsDigest": hashlib.sha256(",".join(response_ids).encode()).hexdigest()[:16],
        "sameAsDefault": response_ids == default_ids,
        "defaultIdsCount": len(default_ids),
        "formMethod": method,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="10,30,50,100")
    args = parser.parse_args()
    with requests.Session() as session:
        for size in [int(x) for x in args.sizes.split(",")]:
            try:
                print(json.dumps(probe(session, size), ensure_ascii=False))
            except Exception as exc:
                print(
                    json.dumps(
                        {"requestedPageUnit": size, "errorType": type(exc).__name__}
                    )
                )
                raise


if __name__ == "__main__":
    main()
