"""Redacted transport fingerprint for small Incheon Office of Education responses.

Diagnostic only. Does not alter collector coverage decisions. Never emits
request headers, response cookie values, or raw CSRF tokens.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

MAX_EXCERPT_SOURCE_BYTES = 512
MAX_EXCERPT_CHARS = 200

_TOKENISH = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")
_URL = re.compile(r"(https?://[^\s'\"<>?#]+)\?[^\s'\"<>]*", re.IGNORECASE)
_SPACE = re.compile(r"\s+")

_KIND_PATTERNS = (
    ("script-redirect", re.compile(r"location\s*(?:\.href)?\s*=|location\.(?:replace|assign)\s*\(", re.I)),
    ("meta-refresh", re.compile(r"http-equiv\s*=\s*['\"]?refresh", re.I)),
    ("block-notice", re.compile(
        r"access\s*denied|forbidden|blocked|rejected|not\s+allowed|firewall|"
        r"차단|허용되지|접근(?:이|을)?\s*(?:제한|거부)|비정상|해외", re.I)),
    ("script-only", re.compile(r"^\s*<script\b", re.I)),
)

def _redact(text: str) -> str:
    text = _URL.sub(lambda m: m.group(1) + "?<query-redacted>", text)
    return _TOKENISH.sub(lambda m: f"<redacted:{len(m.group(0))}>", text)

def classify_body(text: str) -> str:
    if not text.strip():
        return "empty"
    for kind, pattern in _KIND_PATTERNS:
        if pattern.search(text):
            return kind
    return "other"

def transport_fingerprint(response) -> dict:
    content = response.content or b""
    headers = getattr(response, "headers", {}) or {}
    history = list(getattr(response, "history", []) or [])
    cookie_names = sorted({cookie.name for cookie in getattr(response, "cookies", []) or []})
    evidence = {
        "httpStatus": int(getattr(response, "status_code", 0) or 0),
        "responseBytes": len(content),
        "contentType": str(headers.get("Content-Type") or "")[:80],
        "server": str(headers.get("Server") or "")[:60],
        "finalHost": (urlparse(str(getattr(response, "url", "") or "")).hostname or ""),
        "redirectCount": len(history),
        "redirectHosts": [
            urlparse(str(getattr(item, "url", "") or "")).hostname or ""
            for item in history
        ][:5],
        "setCookieNames": cookie_names[:10],
    }
    if len(content) <= MAX_EXCERPT_SOURCE_BYTES:
        body = content.decode(getattr(response, "encoding", None) or "utf-8", errors="replace")
        evidence["bodyKind"] = classify_body(body)
        evidence["bodyExcerpt"] = _redact(_SPACE.sub(" ", body).strip())[:MAX_EXCERPT_CHARS]
    return evidence

def transport_summary(response) -> str:
    """Classification first so truncation doesn't hide diagnostic identity."""
    fp = transport_fingerprint(response)
    parts = []
    if "bodyKind" in fp:
        parts.extend([f"kind={fp['bodyKind']}", f"excerpt={fp['bodyExcerpt']!r}"])
    parts += [
        f"status={fp['httpStatus']}",
        f"bytes={fp['responseBytes']}",
        f"type={fp['contentType'] or '-'}",
        f"server={fp['server'] or '-'}",
        f"host={fp['finalHost'] or '-'}",
    ]
    return " ".join(parts)
