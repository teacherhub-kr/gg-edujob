#!/usr/bin/env python3
"""Canonical strong identities derived only from source-native URL identifiers."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


SEOUL_CMS_DETAIL_RE = re.compile(
    r"^/CMS/(?:[^/?#]+/){2,}(?P<article>[1-9]\d*)_(?P<board>[1-9]\d*)\.html$",
    re.IGNORECASE,
)
SEOUL_JOB_DETAIL_RE = re.compile(r"(?:^|/)JOV\d+\.do$", re.IGNORECASE)
NON_DETAIL_SEGMENTS = {"home", "index", "list", "main", "search"}


def _parsed(raw):
    try:
        parsed = urlparse(str(raw or "").strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def _host(parsed) -> str:
    return (parsed.hostname or "").lower().rstrip(".")


def seoul_cms_detail_id(raw) -> str:
    """Return a strong ID only for a permanent Seoul static-CMS detail path."""
    parsed = _parsed(raw)
    if parsed is None:
        return ""
    match = SEOUL_CMS_DETAIL_RE.fullmatch(parsed.path)
    if not match:
        return ""
    segments = {segment.lower() for segment in parsed.path.split("/") if segment}
    if segments.intersection(NON_DETAIL_SEGMENTS):
        return ""
    return (
        f"seoul-cms:{_host(parsed)}:{match.group('board')}:{match.group('article')}"
    )


def canonical_source_id(job) -> str:
    """Return the canonical strong official source ID, or an empty string."""
    if not isinstance(job, dict):
        return ""

    urls = []
    for key in ("url", "openUrl"):
        raw = str(job.get(key) or "").strip()
        if raw and raw not in urls:
            urls.append(raw)
    parsed_urls = [(raw, parsed) for raw in urls if (parsed := _parsed(raw)) is not None]

    if job.get("sourceType") == "통합게시판":
        for _raw, parsed in parsed_urls:
            query = parse_qs(parsed.query)
            pbanc = str((query.get("pbancSn") or [""])[0])
            if pbanc.isdigit():
                return f"goe-central:{pbanc}"
            recruit = str((query.get("q_rcrtSn") or query.get("rcrtSn") or [""])[0])
            if recruit.isdigit():
                return f"seoul-central:{recruit}"

    province = str(job.get("province") or "")
    if province == "서울":
        seq = str((job.get("openParams") or {}).get("job_seq") or "")
        if seq.isdigit():
            host_source = _parsed(job.get("openUrl") or job.get("url"))
            if host_source is not None and SEOUL_JOB_DETAIL_RE.search(host_source.path):
                return f"seoul:{_host(host_source)}:{seq}"
        for raw, parsed in parsed_urls:
            query_seq = str((parse_qs(parsed.query).get("job_seq") or [""])[0])
            if query_seq.isdigit() and SEOUL_JOB_DETAIL_RE.search(parsed.path):
                return f"seoul:{_host(parsed)}:{query_seq}"
            static_id = seoul_cms_detail_id(raw)
            if static_id:
                return static_id

    if province == "경기":
        field_bbs = str(job.get("bbsId") or "")
        field_ntt = str(job.get("nttSn") or "")
        for _raw, parsed in parsed_urls:
            query = parse_qs(parsed.query)
            bbs = field_bbs or str((query.get("bbsId") or [""])[0])
            ntt = field_ntt or str((query.get("nttSn") or [""])[0])
            if bbs.isdigit() and ntt.isdigit():
                return f"mircms:{_host(parsed)}:{bbs}:{ntt}"
    return ""
