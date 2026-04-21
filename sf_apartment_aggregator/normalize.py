from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


PRICE_RE = re.compile(r"\$?\s*([\d,]+)")
BEDS_RE = re.compile(r"([\d.]+)\s*(?:bd|bed|beds|br)", re.IGNORECASE)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def parse_price(value: str | None) -> int | None:
    if not value:
        return None
    match = PRICE_RE.search(value)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def parse_beds(value: str | None) -> float | None:
    if not value:
        return None
    match = BEDS_RE.search(value)
    if not match:
        return None
    return float(match.group(1))


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query_params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    query = urlencode(sorted(query_params))
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", query, ""))
