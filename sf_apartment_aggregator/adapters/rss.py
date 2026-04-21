from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser

from sf_apartment_aggregator.adapters.base import AdapterError, SourceAdapter
from sf_apartment_aggregator.models import NormalizedListing
from sf_apartment_aggregator.normalize import canonicalize_url, normalize_whitespace, parse_beds, parse_price, utcnow


class RSSSourceAdapter(SourceAdapter):
    def fetch(self) -> list[NormalizedListing]:
        response = self.session.get(str(self.source.url), timeout=self.source.timeout_seconds)
        if response.status_code >= 400:
            raise AdapterError(f"rss_source_http_{response.status_code}")

        parsed = feedparser.parse(response.text)
        listings: list[NormalizedListing] = []
        now = utcnow()
        for entry in parsed.entries:
            listing_url = entry.get("link")
            if not listing_url:
                continue
            published_at = _parse_datetime(entry.get("published"))
            title = normalize_whitespace(entry.get("title")) or "Untitled Listing"
            summary = normalize_whitespace(entry.get("summary"))
            location = normalize_whitespace(entry.get("where") or entry.get("location") or "")
            price = parse_price(entry.get("price") or title or summary)
            beds = parse_beds(title + " " + summary)

            listings.append(
                NormalizedListing(
                    source=self.source.name,
                    source_type="rss",
                    listing_url=listing_url,
                    canonical_url=canonicalize_url(listing_url),
                    external_id=str(entry.get("id")) if entry.get("id") else None,
                    title=title,
                    price=price,
                    beds=beds,
                    location_text=location,
                    neighborhood=None,
                    summary=summary,
                    scraped_at=now,
                    published_at=published_at,
                )
            )
        return listings


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
