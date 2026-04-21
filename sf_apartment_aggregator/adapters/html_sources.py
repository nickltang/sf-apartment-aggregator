from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sf_apartment_aggregator.adapters.base import AdapterError, SourceAdapter
from sf_apartment_aggregator.models import NormalizedListing
from sf_apartment_aggregator.normalize import canonicalize_url, normalize_whitespace, parse_beds, parse_price, utcnow


def _text(element) -> str:
    return normalize_whitespace(element.get_text(" ", strip=True)) if element else ""


class HTMLSourceAdapter(SourceAdapter):
    def fetch(self) -> list[NormalizedListing]:
        response = self.session.get(str(self.source.url), timeout=self.source.timeout_seconds)
        if response.status_code >= 400:
            raise AdapterError(f"html_source_http_{response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")
        selector = self.source.listing_selector or ".listing, .result-row, article"
        listing_nodes = soup.select(selector)

        if not listing_nodes:
            fallback_listings = self._fallback_anchor_listings(soup)
            if fallback_listings:
                return fallback_listings
            raise AdapterError("html_no_listing_nodes")

        now = utcnow()
        listings: list[NormalizedListing] = []
        for node in listing_nodes:
            title_el = node.select_one(self.source.title_selector or ".title, .result-title, h2, h3")
            link_el = node.select_one(self.source.url_selector or "a[href]")
            price_el = node.select_one(self.source.price_selector or ".price")
            beds_el = node.select_one(self.source.beds_selector or ".beds")
            location_el = node.select_one(self.source.location_selector or ".location, .neighborhood")
            summary_el = node.select_one(self.source.summary_selector or "p, .summary, .description")

            if not link_el:
                continue

            listing_url = link_el.get("href", "").strip()
            if not listing_url:
                continue
            if listing_url.startswith("/"):
                listing_url = str(self.source.url).rstrip("/") + listing_url

            title = _text(title_el) or _text(link_el) or "Untitled Listing"
            summary = _text(summary_el)
            location = _text(location_el)
            price = parse_price(_text(price_el) or title or summary)
            beds = parse_beds(_text(beds_el) or title or summary)

            listings.append(
                NormalizedListing(
                    source=self.source.name,
                    source_type="html",
                    listing_url=listing_url,
                    canonical_url=canonicalize_url(listing_url),
                    external_id=node.get("data-id") or None,
                    title=title,
                    price=price,
                    beds=beds,
                    location_text=location,
                    neighborhood=location or None,
                    summary=summary,
                    scraped_at=now,
                    published_at=None,
                )
            )
        return listings

    def _fallback_anchor_listings(self, soup: BeautifulSoup) -> list[NormalizedListing]:
        patterns = [
            "/apartments/rental/",
            "/homes-to-rent/",
            "/listings/detail/",
            "/vacancies/",
        ]
        now = utcnow()
        seen: set[str] = set()
        listings: list[NormalizedListing] = []
        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            if not any(pattern in href for pattern in patterns):
                continue
            listing_url = urljoin(str(self.source.url), href)
            canonical_url = canonicalize_url(listing_url)
            if canonical_url in seen:
                continue
            seen.add(canonical_url)
            title = _text(anchor) or listing_url.rstrip("/").split("/")[-1].replace("-", " ").title() or "Untitled Listing"
            listings.append(
                NormalizedListing(
                    source=self.source.name,
                    source_type="html",
                    listing_url=listing_url,
                    canonical_url=canonical_url,
                    external_id=None,
                    title=title,
                    price=parse_price(title),
                    beds=parse_beds(title),
                    location_text="",
                    neighborhood=None,
                    summary="",
                    scraped_at=now,
                    published_at=None,
                )
            )
        return listings
