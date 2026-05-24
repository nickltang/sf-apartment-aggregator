from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sf_apartment_aggregator.adapters.base import AdapterError, SourceAdapter
from sf_apartment_aggregator.models import NormalizedListing
from sf_apartment_aggregator.normalize import canonicalize_url, normalize_whitespace, parse_beds, parse_price, utcnow


class BrowserCraigslistAdapter(SourceAdapter):
    def fetch(self) -> list[NormalizedListing]:
        profile_dir = self._resolve_profile_dir()
        html = self._fetch_html_via_browser(profile_dir)
        return self.parse_html_document(str(self.source.url), self.source.name, html)

    def _resolve_profile_dir(self) -> Path:
        configured = self.source.browser_profile_dir or os.environ.get("SF_APT_CRAIGSLIST_PROFILE_DIR")
        if not configured:
            raise AdapterError("browser_profile_dir_required")
        return Path(configured).expanduser()

    def _fetch_html_via_browser(self, profile_dir: Path) -> str:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - import dependency guard
            raise AdapterError("playwright_not_installed") from exc

        profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=self.source.browser_headless,
                    executable_path=self.source.browser_executable_path,
                )
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto(str(self.source.url), wait_until="domcontentloaded", timeout=self.source.timeout_seconds * 1000)
                    selector = self.source.listing_selector or ".cl-search-result, .result-row"
                    try:
                        page.wait_for_selector(selector, timeout=self.source.browser_wait_ms)
                    except PlaywrightTimeoutError:
                        # Continue with best-effort HTML capture.
                        pass
                    return page.content()
                finally:
                    context.close()
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"browser_fetch_failed:{exc}") from exc

    @staticmethod
    def parse_html_document(base_url: str, source_name: str, html: str) -> list[NormalizedListing]:
        soup = BeautifulSoup(html, "html.parser")
        now = utcnow()
        listings: list[NormalizedListing] = []
        seen: set[str] = set()

        nodes = soup.select(".cl-search-result, .result-row")
        for node in nodes:
            link_el = node.select_one("a.posting-title, a.cl-app-anchor.text-only, a.cl-app-anchor, a.result-title, a[href*='/apa/'], a[href]")
            if not link_el:
                continue
            href = (link_el.get("href") or "").strip()
            if not href:
                continue
            listing_url = urljoin(base_url, href)
            canonical_url = canonicalize_url(listing_url)
            if canonical_url in seen:
                continue
            seen.add(canonical_url)

            title_el = node.select_one(".posting-title .label, .label, .result-title")
            title = normalize_whitespace((title_el.get_text(" ", strip=True) if title_el else "") or link_el.get_text(" ", strip=True) or node.get("title")) or "Untitled Listing"
            price_el = node.select_one(".priceinfo, .result-price")
            housing_el = node.select_one(".post-bedrooms, .housing-meta .post-bedrooms, .housing, .result-meta .housing")
            location_el = node.select_one(".result-location, .meta .location, .result-hood, .location")
            price_text = normalize_whitespace(price_el.get_text(" ", strip=True)) if price_el else ""
            housing_text = normalize_whitespace(housing_el.get_text(" ", strip=True)) if housing_el else ""
            location_text = normalize_whitespace(location_el.get_text(" ", strip=True)) if location_el else ""
            summary = normalize_whitespace(node.get_text(" ", strip=True))
            external_id = node.get("data-pid")

            listings.append(
                NormalizedListing(
                    source=source_name,
                    source_type="browser",
                    listing_url=listing_url,
                    canonical_url=canonical_url,
                    external_id=external_id,
                    title=title,
                    price=parse_price(price_text or title),
                    beds=parse_beds(housing_text or title),
                    location_text=location_text,
                    neighborhood=location_text or None,
                    summary=summary,
                    scraped_at=now,
                    published_at=None,
                )
            )
        if not listings:
            raise AdapterError(BrowserCraigslistAdapter._classify_empty_result_page(soup))
        return listings

    @staticmethod
    def _classify_empty_result_page(soup: BeautifulSoup) -> str:
        page_text = normalize_whitespace(soup.get_text(" ", strip=True)).lower()
        page_title = normalize_whitespace(soup.title.get_text(" ", strip=True) if soup.title else "").lower()

        challenge_markers = [
            "are you human",
            "human verification",
            "verify you are human",
            "press and hold",
            "security check",
            "complete the captcha",
            "captcha",
        ]
        if any(marker in page_text or marker in page_title for marker in challenge_markers):
            return "craigslist_challenge_page"

        blocked_markers = [
            "your request has been blocked",
            "request has been blocked",
        ]
        if any(marker in page_text or marker in page_title for marker in blocked_markers):
            return "craigslist_blocked_page"

        no_results_markers = [
            "no results found",
            "there are no results",
            "zero local results found",
        ]
        if any(marker in page_text for marker in no_results_markers):
            return "craigslist_no_results"

        if soup.select("form[action*='captcha']") or soup.select("iframe[src*='captcha']"):
            return "craigslist_challenge_page"

        return "craigslist_selector_mismatch"
