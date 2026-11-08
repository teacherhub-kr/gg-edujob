#!/usr/bin/env python3
"""Read-only ICE page-size probe. Never asserts complete coverage or writes jobs."""
import argparse
import json
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE = "https://www.ice.go.kr"
PATH = "/ice/na/ntt/selectNttList.do"
PARAMS = {"bbsId": "1981", "mi": "10997"}
ID_PATTERN = re.compile(r"(?:selectNttInfo|nttSn[=,'\\\" ]+)(?:[^0-9]{0,25})([0-9]{5,})", re.I)


def ids(html):
    return sorted(set(ID_PATTERN.findall(html)))


def probe(session, size):
    url = urljoin(BASE, PATH)
    first = session.get(url, params=PARAMS, timeout=(8, 25))
    first.raise_for_status()
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
    response = session.post(action, data=fields, timeout=(8, 25)) if method == "POST" else session.get(action, params=fields, timeout=(8, 25))
    response.raise_for_status()
    return {"requestedPageUnit": size, "status": response.status_code,
            "responseBytes": len(response.content), "idsCount": len(ids(response.text)),
            "idsDigest": __import__("hashlib").sha256(",".join(ids(response.text)).encode()).hexdigest()[:16],
            "sameAsDefault": ids(response.text) == ids(first.text),
            "defaultIdsCount": len(ids(first.text)), "formMethod": method}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="10,30,50,100")
    args = parser.parse_args()
    with requests.Session() as session:
        for size in [int(x) for x in args.sizes.split(",")]:
            try:
                print(json.dumps(probe(session, size), ensure_ascii=False))
            except Exception as exc:
                print(json.dumps({"requestedPageUnit": size, "errorType": type(exc).__name__}))
                raise


if __name__ == "__main__":
    main()
