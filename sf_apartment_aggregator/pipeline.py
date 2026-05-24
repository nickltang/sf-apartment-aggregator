from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from sf_apartment_aggregator.adapters import (
    AdapterError,
    BrowserCraigslistAdapter,
    GaetaniCollectionAdapter,
    HTMLSourceAdapter,
    RentSFNowAjaxAdapter,
    RSSSourceAdapter,
)
from sf_apartment_aggregator.config import AppConfig, SourceConfig
from sf_apartment_aggregator.filters import ListingFilter
from sf_apartment_aggregator.models import NormalizedListing, SourceRunResult
from sf_apartment_aggregator.normalize import normalize_whitespace, parse_beds, utcnow
from sf_apartment_aggregator.notifier import DiscordNotifier, NotificationError
from sf_apartment_aggregator.repository import SQLiteRepository

LOGGER = logging.getLogger("sf_apartment_aggregator")


class PollPipeline:
    def __init__(self, config: AppConfig, repository: SQLiteRepository, session: requests.Session | None = None):
        self.config = config
        self.repository = repository
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self.filter_engine = ListingFilter(config.filters)
        self.strict_webhook_url = (
            str(config.discord.strict_webhook_url)
            if config.discord.strict_webhook_url
            else (str(config.discord.webhook_url) if config.discord.webhook_url else None)
        )
        self.broad_webhook_url = str(config.discord.broad_webhook_url) if config.discord.broad_webhook_url else None
        self.notifier = DiscordNotifier(self.strict_webhook_url, self.session)
        self._craigslist_enriched: set[str] = set()

    def run_cycle(self, *, alerting_enabled: bool) -> dict:
        if not self._is_in_active_hours():
            summary = {
                "ran_at": datetime.utcnow().isoformat() + "Z",
                "skipped": True,
                "reason": "outside_active_hours",
                "active_timezone": self.config.active_timezone,
                "active_start_hour": self.config.active_start_hour,
                "active_end_hour": self.config.active_end_hour,
            }
            LOGGER.info("poll_skipped", extra={"event": "poll_skipped", "data": summary})
            return summary

        first_run_seed = self.repository.is_first_run() and alerting_enabled
        total_new = 0
        total_alerted = 0
        total_matched = 0
        source_results: list[SourceRunResult] = []

        for source in self.config.sources:
            LOGGER.info(
                "source_started",
                extra={
                    "event": "source_started",
                    "data": {"source": source.name, "source_type": source.type, "url": str(source.url)},
                },
            )
            started = utcnow()
            fetched = 0
            parsed = 0
            new_count = 0
            matched_count = 0
            alerted_count = 0
            success = True
            error_message = None
            alert_errors: list[str] = []
            skip_reason = self._source_skip_reason(source, started)

            if skip_reason:
                finished = utcnow()
                result = SourceRunResult(
                    source=source.name,
                    source_type=source.type,
                    started_at=started,
                    finished_at=finished,
                    success=True,
                    fetched_count=0,
                    parsed_count=0,
                    new_count=0,
                    matched_count=0,
                    alerted_count=0,
                    error_message=skip_reason,
                )
                self.repository.record_source_run(result)
                source_results.append(result)
                LOGGER.info(
                    "source_skipped",
                    extra={
                        "event": "source_skipped",
                        "data": {"source": source.name, "reason": skip_reason},
                    },
                )
                LOGGER.info(
                    "source_finished",
                    extra={
                        "event": "source_finished",
                        "data": {
                            "source": source.name,
                            "source_type": source.type,
                            "success": True,
                            "fetched_count": 0,
                            "parsed_count": 0,
                            "new_count": 0,
                            "matched_count": 0,
                            "alerted_count": 0,
                            "error": skip_reason,
                        },
                    },
                )
                continue

            try:
                listings = self._fetch_source_with_retries(source)
                fetched = len(listings)
                parsed = len(listings)
                for listing in listings:
                    if source.name == "craigslist_sf" and source.enrich_detail_pages:
                        self._enrich_craigslist_listing(listing)
                    inferred = self.filter_engine.infer_neighborhood(listing)
                    if inferred:
                        listing.neighborhood = inferred
                    filter_result = self.filter_engine.evaluate(listing)
                    outcome = self.repository.upsert_listing(listing, filter_result)
                    if outcome.is_new:
                        new_count += 1

                    if filter_result.matched:
                        matched_count += 1
                    if outcome.is_new and alerting_enabled and not first_run_seed:
                        broad_result = self.filter_engine.evaluate_broad(listing)
                        if (
                            self.broad_webhook_url
                            and broad_result.matched
                            and not self.repository.has_alert_for(outcome.canonical_url, "broad")
                        ):
                            broad_payload = self.notifier.build_payload(listing, stream="broad")
                            try:
                                self.notifier.send(broad_payload, webhook_url=self.broad_webhook_url)
                            except NotificationError as exc:
                                alert_errors.append(f"broad:{outcome.canonical_url}:{exc}")
                                LOGGER.error(
                                    "alert_send_failed",
                                    extra={
                                        "event": "alert_send_failed",
                                        "data": {
                                            "source": source.name,
                                            "canonical_url": outcome.canonical_url,
                                            "alert_type": "broad",
                                            "error": str(exc),
                                        },
                                    },
                                )
                            else:
                                self.repository.record_alert(outcome.canonical_url, broad_payload, listing.scraped_at, "broad")
                                alerted_count += 1
                        if (
                            self.strict_webhook_url
                            and filter_result.matched
                            and not self.repository.has_alert_for(outcome.canonical_url, "strict")
                        ):
                            strict_payload = self.notifier.build_payload(listing, stream="strict")
                            try:
                                self.notifier.send(strict_payload, webhook_url=self.strict_webhook_url)
                            except NotificationError as exc:
                                alert_errors.append(f"strict:{outcome.canonical_url}:{exc}")
                                LOGGER.error(
                                    "alert_send_failed",
                                    extra={
                                        "event": "alert_send_failed",
                                        "data": {
                                            "source": source.name,
                                            "canonical_url": outcome.canonical_url,
                                            "alert_type": "strict",
                                            "error": str(exc),
                                        },
                                    },
                                )
                            else:
                                self.repository.record_alert(outcome.canonical_url, strict_payload, listing.scraped_at, "strict")
                                alerted_count += 1

            except Exception as exc:  # intentionally broad to keep cycle alive per source
                success = False
                error_message = str(exc)
                self.repository.record_parse_error(source.name, str(source.url), str(exc), utcnow())
                LOGGER.error(
                    "source_failed",
                    extra={"event": "source_failed", "data": {"source": source.name, "error": str(exc)}},
                )

            finished = utcnow()
            result = SourceRunResult(
                source=source.name,
                source_type=source.type,
                started_at=started,
                finished_at=finished,
                success=success,
                fetched_count=fetched,
                parsed_count=parsed,
                new_count=new_count,
                matched_count=matched_count,
                alerted_count=alerted_count,
                error_message=error_message or ("; ".join(alert_errors) if alert_errors else None),
            )
            self.repository.record_source_run(result)
            source_results.append(result)
            total_new += new_count
            total_matched += matched_count
            total_alerted += alerted_count
            LOGGER.info(
                "source_finished",
                extra={
                    "event": "source_finished",
                    "data": {
                        "source": source.name,
                        "source_type": source.type,
                        "success": success,
                        "fetched_count": fetched,
                        "parsed_count": parsed,
                        "new_count": new_count,
                        "matched_count": matched_count,
                        "alerted_count": alerted_count,
                        "error": error_message,
                    },
                },
            )

        summary = {
            "ran_at": datetime.utcnow().isoformat() + "Z",
            "first_run_seed": first_run_seed,
            "sources": len(self.config.sources),
            "new_listings": total_new,
            "matched": total_matched,
            "alerted": total_alerted,
            "source_results": [asdict(r) for r in source_results],
        }
        LOGGER.info("poll_summary", extra={"event": "poll_summary", "data": summary})
        return summary

    def _fetch_source_with_retries(self, source: SourceConfig):
        last_error: Exception | None = None
        attempts = max(1, source.retries + 1)
        for _ in range(attempts):
            try:
                adapter = self._adapter_for(source)
                return adapter.fetch()
            except AdapterError as exc:
                last_error = exc
            except requests.RequestException as exc:
                last_error = exc
        if last_error is None:
            raise RuntimeError("source_fetch_failed")
        raise last_error

    def _adapter_for(self, source: SourceConfig):
        if source.name == "rentsfnow":
            return RentSFNowAjaxAdapter(source, self.session)
        if source.name == "gaetani":
            return GaetaniCollectionAdapter(source, self.session)
        if source.type == "rss":
            return RSSSourceAdapter(source, self.session)
        if source.type == "browser":
            return BrowserCraigslistAdapter(source, self.session)
        return HTMLSourceAdapter(source, self.session)

    def _enrich_craigslist_listing(self, listing: NormalizedListing) -> None:
        if listing.canonical_url in self._craigslist_enriched:
            return
        self._craigslist_enriched.add(listing.canonical_url)
        try:
            response = self.session.get(listing.listing_url, timeout=8)
            if response.status_code >= 400:
                return
            soup = BeautifulSoup(response.text, "html.parser")
            address = normalize_whitespace((soup.select_one(".mapaddress") or {}).get_text(" ", strip=True) if soup.select_one(".mapaddress") else "")
            body = normalize_whitespace((soup.select_one("#postingbody") or {}).get_text(" ", strip=True) if soup.select_one("#postingbody") else "")
            attrs = normalize_whitespace(" ".join(el.get_text(" ", strip=True) for el in soup.select(".attrgroup span")))
            if address:
                if listing.location_text:
                    if address.lower() not in listing.location_text.lower():
                        listing.location_text = f"{listing.location_text} | {address}"
                else:
                    listing.location_text = address
                if not listing.neighborhood:
                    listing.neighborhood = address
            if body:
                listing.summary = body
            if listing.beds is None:
                beds = parse_beds(attrs or body or listing.title)
                if beds is not None:
                    listing.beds = beds
        except Exception:
            return

    def _is_in_active_hours(self) -> bool:
        now = datetime.now(ZoneInfo(self.config.active_timezone))
        hour = now.hour
        start = self.config.active_start_hour
        end = self.config.active_end_hour
        if start == end:
            return True
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def _source_skip_reason(self, source: SourceConfig, started_at: datetime) -> str | None:
        latest_run = self.repository.get_latest_source_run(source.name)
        if not latest_run:
            return None

        finished_at_raw = latest_run.get("finished_at")
        if not finished_at_raw:
            return None
        try:
            finished_at = datetime.fromisoformat(finished_at_raw)
        except ValueError:
            return None

        if source.min_poll_interval_minutes is not None:
            next_allowed_at = finished_at + timedelta(minutes=source.min_poll_interval_minutes)
            if started_at < next_allowed_at:
                return "source_rate_limited_recent_run"

        error_message = latest_run.get("error_message") or ""
        if source.cooldown_on_block_minutes and "craigslist_blocked_page" in error_message:
            next_allowed_at = finished_at + timedelta(minutes=source.cooldown_on_block_minutes)
            if started_at < next_allowed_at:
                return "source_cooldown_after_block"

        return None
