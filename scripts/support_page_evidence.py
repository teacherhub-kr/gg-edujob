#!/usr/bin/env python3
"""Structured official-page evidence parsers for support-office audits."""
from __future__ import annotations

import io
import hashlib
import re
import struct
import zlib
import zipfile
from calendar import monthrange
from datetime import date
from urllib.parse import urljoin
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from support_reviewed_binary_evidence import REVIEWED_BINARY_EVIDENCE


DATE_RE = re.compile(
    r"(?<!\d)(?:(20\s*\d{2}|\d{2})\s*[.\-/년]\s*)?"
    r"(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*\.?\s*(?:일)?"
)
APPLICATION_ANCHOR_RE = re.compile(
    r"(?:원서|서류|응시원서|지원서|신청서|채용서류)?\s*"
    r"접수\s*(?:[가-힣]\s*[.)]\s*)?(?:기간|일정|기한|마감|일시)"
    r"|(?:원서|서류|응시원서|지원서|신청서)\s*접수\s*:"
    r"|접수\s*:\s*(?=20\s*\d{2})|응시원서\s*:|모집\s*기간"
    r"|응시자\s*접수|공고\s*기간"
)
ACTIVITY_ANCHOR_RE = re.compile(r"(?:채용|계약|근무|활동|운영|위촉)\s*(?:기간|일정)")
INDEFINITE_RE = re.compile(r"(?:채용|충원)\s*시(?:까지)?")
OUTCOME_TITLE_RE = re.compile(
    r"최종\s*합격자|면접\s*(?:심사\s*)?대상자|서류\s*전형\s*합격자|"
    r"채용\s*(?:결과|취소)|모집\s*(?:결과|취소)|선정\s*(?:기관\s*)?결과"
)
EXPLICIT_END_RE = re.compile(
    r"채용\s*공고.{0,30}취소|모집.{0,30}취소|접수.{0,15}마감(?:되었|됐)"
)
MIRCMS_ATTACHMENT_RE = re.compile(
    r"DEXT5UPLOAD\.AddUploadedFile\(\s*[\"'`][^\"'`]*[\"'`]\s*,\s*"
    r"[\"'`](.*?)[\"'`]\s*,\s*[\"'`](.*?)[\"'`]",
    re.DOTALL,
)
SEOUL_DETAIL_RE = re.compile(r"^seoul:[^:]+:(\d+)$")
MIRCMS_DETAIL_RE = re.compile(r"^mircms:[^:]+:\d+:\d+$")


def normalize_text(value):
    return " ".join(str(value or "").split())


def dates_in(value, *, base_year=2026):
    found = []
    year = base_year
    for raw_year, raw_month, raw_day in DATE_RE.findall(value):
        if raw_year:
            year = int(re.sub(r"\s", "", raw_year))
            if year < 100:
                year += 2000
        try:
            found.append(date(year, int(raw_month), int(raw_day)))
        except ValueError:
            continue
    return found


def anchored_period_dates(text, anchors, *, base_year=2026, skip_indefinite=True):
    candidates = []
    for match in anchors.finditer(text):
        snippet = text[match.start() : match.start() + 220]
        parsed = dates_in(snippet, base_year=base_year)
        indefinite = INDEFINITE_RE.search(snippet[:120]) if skip_indefinite else None
        date_matches = list(DATE_RE.finditer(snippet))
        # "기간: 채용 시까지" is open-ended.  A later contingency such as
        # "6.11~6.16, 미충원 시까지" must not erase the explicit closed range.
        if indefinite and (len(parsed) < 2 or len(date_matches) < 2 or indefinite.start() < date_matches[1].end()):
            continue
        if parsed:
            candidates.append((parsed[:2], normalize_text(snippet[:180])))
    return max(candidates, key=lambda item: max(item[0])) if candidates else None


def anchored_period_end(text, anchors, *, base_year=2026):
    period = anchored_period_dates(text, anchors, base_year=base_year)
    return (max(period[0]), period[1]) if period else None


def _hwp_text(payload):
    import olefile

    document = olefile.OleFileIO(io.BytesIO(payload))
    flags = struct.unpack("<I", document.openstream("FileHeader").read()[36:40])[0]
    paragraphs = []
    if document.exists("PrvText"):
        paragraphs.append(document.openstream("PrvText").read().decode("utf-16le", "ignore"))
    sections = sorted(
        "/".join(path)
        for path in document.listdir()
        if path[0] == "BodyText" and path[-1].startswith("Section")
    )
    for section in sections:
        stream = document.openstream(section).read()
        if flags & 1:
            stream = zlib.decompress(stream, -15)
        position = 0
        while position + 4 <= len(stream):
            header = struct.unpack("<I", stream[position : position + 4])[0]
            position += 4
            tag = header & 0x3FF
            size = (header >> 20) & 0xFFF
            if size == 0xFFF:
                size = struct.unpack("<I", stream[position : position + 4])[0]
                position += 4
            record = stream[position : position + size]
            position += size
            if tag == 67:
                paragraphs.append(record.decode("utf-16le", "ignore"))
    cleaned = " ".join(paragraphs)
    return normalize_text("".join(char if ord(char) >= 32 else " " for char in cleaned))


def _hwpx_text(payload):
    paragraphs = []
    with zipfile.ZipFile(io.BytesIO(payload)) as document:
        for name in document.namelist():
            if not re.fullmatch(r"Contents/section\d+\.xml", name, re.IGNORECASE):
                continue
            root = ElementTree.fromstring(document.read(name))
            paragraphs.extend(node.text or "" for node in root.iter())
    return normalize_text(" ".join(paragraphs))


def _pdf_text(payload):
    from pypdf import PdfReader

    return normalize_text(" ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(payload)).pages))


def attachment_text(payload, name):
    lowered = name.lower()
    if lowered.endswith(".hwp"):
        return _hwp_text(payload)
    if lowered.endswith(".hwpx"):
        return _hwpx_text(payload)
    if lowered.endswith(".pdf"):
        return _pdf_text(payload)
    return ""


def attachment_links(soup, html, page_url):
    links = [(name, urljoin(page_url, path)) for name, path in MIRCMS_ATTACHMENT_RE.findall(html)]
    for anchor in soup.find_all("a", href=True):
        if "fileDownload.do" in anchor["href"]:
            links.append((normalize_text(anchor.get_text(" ", strip=True)), urljoin(page_url, anchor["href"])))
    return links


def reviewed_binary_evidence(soup, html, strong_id, page_url, *, as_of, attachment_loader):
    """Use human-reviewed image/PDF evidence only while its official bytes are unchanged."""
    record = REVIEWED_BINARY_EVIDENCE.get(strong_id)
    if not record:
        return None
    page_links = {urljoin(page_url, node["src"]) for node in soup.find_all("img", src=True)}
    page_links.update(urljoin(page_url, node["href"]) for node in soup.find_all("a", href=True))
    page_links.update(link for _name, link in attachment_links(soup, html, page_url))
    artifact_url = record.get("artifactUrl")
    if artifact_url not in page_links:
        return None
    try:
        payload = attachment_loader(artifact_url, page_url)
    except Exception:
        return None
    if hashlib.sha256(payload).hexdigest() != record.get("sha256"):
        return None
    value = date.fromisoformat(record["date"])
    if record["kind"] == "ended" and value >= as_of:
        return None
    return _evidence(
        record["kind"],
        evidence=f"mircms-reviewed-binary:{record['basis']}",
        value=value,
        snippet=record.get("note", ""),
    )


def _evidence(kind, *, evidence, value=None, snippet=""):
    result = {"kind": kind, "evidence": evidence}
    if value is not None:
        result["date"] = value.isoformat()
    if snippet:
        result["snippet"] = snippet
    return result


def _text_evidence(text, *, prefix, base_year, as_of):
    deadline = anchored_period_end(text, APPLICATION_ANCHOR_RE, base_year=base_year)
    if deadline:
        return _evidence("deadline", evidence=f"{prefix}:application-deadline", value=deadline[0], snippet=deadline[1])
    if EXPLICIT_END_RE.search(text):
        return _evidence("ended", evidence=f"{prefix}:explicit-end")
    activity = anchored_period_dates(
        text, ACTIVITY_ANCHOR_RE, base_year=base_year, skip_indefinite=False
    )
    if activity and min(activity[0]) < as_of:
        return _evidence(
            "ended",
            evidence=f"{prefix}:activity-period-started",
            value=min(activity[0]),
            snippet=activity[1],
        )
    privacy_anchor = "운영인력 채용을 위한 본인 확인 및 심사자료"
    privacy_at = text.find(privacy_anchor)
    if privacy_at >= 0:
        privacy_dates = dates_in(text[privacy_at : privacy_at + 350], base_year=base_year)
        if privacy_dates and max(privacy_dates[:2]) < as_of:
            return _evidence("ended", evidence=f"{prefix}:recruitment-data-retention-ended", value=max(privacy_dates[:2]))
    return None


def _record_title(soup):
    for selector in ("th.title", ".bbsV_tit", ".bbsV_title", ".bbs_ViewA .title"):
        node = soup.select_one(selector)
        if node:
            return normalize_text(node.get_text(" ", strip=True))
    first = soup.select_one(".bbs_ViewA")
    return normalize_text(first.get_text(" ", strip=True)) if first else ""


def _registered_year(soup, default):
    for label in soup.find_all(["th", "strong"]):
        if normalize_text(label.get_text(" ", strip=True)) != "등록일":
            continue
        value = label.find_next_sibling(["td", "span"])
        parsed = dates_in(value.get_text(" ", strip=True) if value else "", base_year=default)
        if parsed:
            return parsed[0].year
    return default


def parse_mircms(soup, html, strong_id, page_url, *, as_of, attachment_loader):
    if not soup.select_one("#nttViewForm") and not soup.select_one(".bbs_ViewA") and not soup.select_one("tr.cont"):
        return None
    base_year = _registered_year(soup, as_of.year)
    title = _record_title(soup)
    if OUTCOME_TITLE_RE.search(title):
        return _evidence("ended", evidence="mircms:title-outcome")
    content = soup.select_one(".bbsV_cont") or soup.select_one("tr.cont td")
    page_text = normalize_text(content.get_text(" ", strip=True) if content else "")
    evidence = _text_evidence(page_text, prefix="mircms-page", base_year=base_year, as_of=as_of)
    if evidence:
        return evidence
    for name, link in attachment_links(soup, html, page_url):
        try:
            text = attachment_text(attachment_loader(link, page_url), name)
        except Exception:
            continue
        evidence = _text_evidence(text, prefix=f"mircms-attachment:{name}", base_year=base_year, as_of=as_of)
        if evidence:
            return evidence
        if OUTCOME_TITLE_RE.search(text[:500]):
            return _evidence("ended", evidence=f"mircms-attachment:{name}:outcome")
    return reviewed_binary_evidence(
        soup, html, strong_id, page_url, as_of=as_of, attachment_loader=attachment_loader
    )


def parse_seoul_jov(soup, html, strong_id, *, as_of, attachment_loader, page_url):
    expected = SEOUL_DETAIL_RE.fullmatch(strong_id)
    job_seq = soup.select_one("input#job_seq")
    if not expected or not job_seq:
        return None
    if not str(job_seq.get("value") or "").strip():
        return _evidence("ended", evidence="seoul-jov:empty-detail-record")
    if job_seq.get("value") != expected.group(1):
        return None
    base_year = _registered_year(soup, as_of.year)
    for label in soup.find_all("th"):
        if normalize_text(label.get_text(" ", strip=True)) != "마감일":
            continue
        value = label.find_next_sibling("td")
        parsed = dates_in(value.get_text(" ", strip=True) if value else "", base_year=base_year)
        if parsed:
            return _evidence("deadline", evidence="seoul-jov:deadline-field", value=max(parsed))
    appointment = soup.select_one("input#is_appointment")
    if appointment and appointment.get("value") == "1":
        return _evidence("ended", evidence="seoul-jov:is_appointment=1")
    content = ""
    has_registered = False
    for label in soup.find_all("th"):
        label_text = normalize_text(label.get_text(" ", strip=True))
        value = label.find_next_sibling("td")
        if label_text == "등록일" and value and normalize_text(value.get_text(" ", strip=True)):
            has_registered = True
        if label_text == "내용" and value:
            content = normalize_text(value.get_text(" ", strip=True))
    if not has_registered:
        return _evidence("ended", evidence="seoul-jov:empty-detail-record")
    evidence = _text_evidence(content, prefix="seoul-jov-page", base_year=base_year, as_of=as_of)
    if evidence:
        return evidence
    interview = re.search(r"면접.{0,100}?(\d{1,2})월\s*(초|중순|말)?", content)
    if interview:
        month = int(interview.group(1))
        day = {"초": 10, "중순": 20, "말": monthrange(base_year, month)[1]}.get(interview.group(2), monthrange(base_year, month)[1])
        event_date = date(base_year, month, day)
        if event_date < as_of:
            return _evidence("ended", evidence="seoul-jov:selection-event-ended", value=event_date)
    for name, link in attachment_links(soup, html, page_url):
        try:
            text = attachment_text(attachment_loader(link, page_url), name)
        except Exception:
            continue
        evidence = _text_evidence(text, prefix=f"seoul-jov-attachment:{name}", base_year=base_year, as_of=as_of)
        if evidence:
            return evidence
    return None


def official_page_evidence(html, strong_id, page_url, *, as_of, attachment_loader):
    soup = BeautifulSoup(html, "html.parser")
    if MIRCMS_DETAIL_RE.fullmatch(strong_id):
        return parse_mircms(soup, html, strong_id, page_url, as_of=as_of, attachment_loader=attachment_loader)
    if SEOUL_DETAIL_RE.fullmatch(strong_id):
        return parse_seoul_jov(soup, html, strong_id, as_of=as_of, attachment_loader=attachment_loader, page_url=page_url)
    return None
