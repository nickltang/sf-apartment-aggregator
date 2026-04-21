from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sf_apartment_aggregator.adapters.base import AdapterError, SourceAdapter
from sf_apartment_aggregator.models import NormalizedListing
from sf_apartment_aggregator.normalize import canonicalize_url, normalize_whitespace, parse_beds, parse_price, utcnow


def _text(element) -> str:
    return normalize_whitespace(element.get_text(" ", strip=True)) if element else ""


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None


def _parse_dollar_price(value: str | None) -> int | None:
    if not value:
        return None
    matches = re.findall(r"\$\s*([\d,]+)", value)
    if not matches:
        return None
    digits = matches[-1].replace(",", "")
    if not digits.isdigit():
        return None
    return int(digits)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class RentSFNowAjaxAdapter(SourceAdapter):
    def fetch(self) -> list[NormalizedListing]:
        response = self.session.post(
            str(self.source.url),
            data={"action": "wpas_ajax_load", "page": "1", "type": "search"},
            timeout=self.source.timeout_seconds,
        )
        if response.status_code >= 400:
            raise AdapterError(f"rentsfnow_http_{response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select(".apartment.searchListingContainer, .apartment[id^='post-']")
        if not rows:
            raise AdapterError("rentsfnow_no_listing_nodes")

        now = utcnow()
        listings: list[NormalizedListing] = []
        for row in rows:
            link = row.select_one("a[href*='/apartments/rental/'], a[href]")
            if not link:
                continue
            href = (link.get("href") or "").strip()
            if not href:
                continue
            listing_url = urljoin("https://www.rentsfnow.com", href)

            title = _text(row.select_one("h2")) or _text(link) or "Untitled Listing"
            location = _text(row.select_one("h3"))
            info_text = _text(row.select_one(".apartment-info"))
            summary = normalize_whitespace(f"{location} {info_text}")

            external_id = None
            row_id = row.get("id")
            if row_id and row_id.startswith("post-"):
                external_id = row_id.removeprefix("post-")

            listings.append(
                NormalizedListing(
                    source=self.source.name,
                    source_type="api",
                    listing_url=listing_url,
                    canonical_url=canonicalize_url(listing_url),
                    external_id=external_id,
                    title=title,
                    price=_parse_dollar_price(info_text) or parse_price(info_text),
                    beds=parse_beds(info_text),
                    location_text=location,
                    neighborhood=location or None,
                    summary=summary,
                    scraped_at=now,
                    published_at=None,
                )
            )
        if not listings:
            raise AdapterError("rentsfnow_no_parsed_listings")
        return listings


class GaetaniCollectionAdapter(SourceAdapter):
    def fetch(self) -> list[NormalizedListing]:
        response = self.session.get(str(self.source.url), timeout=self.source.timeout_seconds)
        if response.status_code >= 400:
            raise AdapterError(f"gaetani_http_{response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise AdapterError("gaetani_invalid_json") from exc

        values = payload.get("values") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            raise AdapterError("gaetani_missing_values")

        now = utcnow()
        listings: list[NormalizedListing] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            data = item.get("data")
            if not isinstance(data, dict):
                continue
            uid = data.get("listable_uid")
            if not uid:
                continue

            listing_url = f"https://www.gaetanirealestate.com/listings/detail/{uid}"
            title = normalize_whitespace(data.get("marketing_title") or data.get("full_address") or "Untitled Listing")
            location = normalize_whitespace(data.get("address_city") or data.get("full_address") or "")
            summary_raw = data.get("marketing_description") or data.get("meta_description") or ""
            summary = normalize_whitespace(BeautifulSoup(summary_raw, "html.parser").get_text(" ", strip=True))
            price = data.get("market_rent")
            beds = data.get("bedrooms")

            listings.append(
                NormalizedListing(
                    source=self.source.name,
                    source_type="api",
                    listing_url=listing_url,
                    canonical_url=canonicalize_url(listing_url),
                    external_id=str(uid),
                    title=title,
                    price=int(price) if isinstance(price, (int, float)) else parse_price(str(price) if price is not None else None),
                    beds=float(beds) if isinstance(beds, (int, float)) else parse_beds(str(beds) if beds is not None else None),
                    location_text=location,
                    neighborhood=location or None,
                    summary=summary,
                    scraped_at=now,
                    published_at=_parse_iso_datetime(data.get("posted_to_website_at")),
                )
            )
        if not listings:
            raise AdapterError("gaetani_no_listings")
        return listings
