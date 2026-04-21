from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime

import requests

from sf_apartment_aggregator.adapters import AdapterError, HTMLSourceAdapter, RSSSourceAdapter
from sf_apartment_aggregator.config import AppConfig, SourceConfig
from sf_apartment_aggregator.filters import ListingFilter
from sf_apartment_aggregator.models import SourceRunResult
from sf_apartment_aggregator.normalize import utcnow
from sf_apartment_aggregator.notifier import DiscordNotifier
from sf_apartment_aggregator.repository import SQLiteRepository

LOGGER = logging.getLogger("sf_apartment_aggregator")


class PollPipeline:
    def __init__(self, config: AppConfig, repository: SQLiteRepository, session: requests.Session | None = None):
        self.config = config
        self.repository = repository
        self.session = session or requests.Session()
        self.filter_engine = ListingFilter(config.filters)
        self.notifier = DiscordNotifier(str(config.discord.webhook_url) if config.discord.webhook_url else None, self.session)

    def run_cycle(self, *, alerting_enabled: bool) -> dict:
        first_run_seed = self.repository.is_first_run() and alerting_enabled
        total_new = 0
        total_alerted = 0
        total_matched = 0
        source_results: list[SourceRunResult] = []

        for source in self.config.sources:
            started = utcnow()
            fetched = 0
            parsed = 0
            new_count = 0
            matched_count = 0
            alerted_count = 0
            success = True
            error_message = None

            try:
                listings = self._fetch_source_with_retries(source)
                fetched = len(listings)
                parsed = len(listings)
                for listing in listings:
                    filter_result = self.filter_engine.evaluate(listing)
                    outcome = self.repository.upsert_listing(listing, filter_result)
                    if outcome.is_new:
                        new_count += 1

                    if filter_result.matched:
                        matched_count += 1
                        if (
                            outcome.is_new
                            and alerting_enabled
                            and not first_run_seed
                            and not self.repository.has_alert_for(outcome.canonical_url)
                        ):
                            payload = self.notifier.build_payload(listing)
                            self.notifier.send(payload)
                            self.repository.record_alert(outcome.canonical_url, payload, listing.scraped_at)
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
                error_message=error_message,
            )
            self.repository.record_source_run(result)
            source_results.append(result)
            total_new += new_count
            total_matched += matched_count
            total_alerted += alerted_count

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
        if source.type == "rss":
            return RSSSourceAdapter(source, self.session)
        return HTMLSourceAdapter(source, self.session)
