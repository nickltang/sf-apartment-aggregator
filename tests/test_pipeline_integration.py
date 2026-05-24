from __future__ import annotations

import logging
from unittest.mock import patch

import requests

from sf_apartment_aggregator.pipeline import PollPipeline
from sf_apartment_aggregator.normalize import utcnow
from sf_apartment_aggregator.repository import SQLiteRepository


class DummyResponse:
    def __init__(self, text: str = "", status_code: int = 200, headers: dict | None = None, json_data: dict | None = None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}
        self._json_data = json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


class SessionMock(requests.Session):
    def __init__(self, rss_text: str, html_text: str):
        super().__init__()
        self.rss_text = rss_text
        self.html_text = html_text
        self.sent_payloads: list[dict] = []

    def get(self, url, timeout=None, **kwargs):  # noqa: ANN001
        if str(url).endswith("feed.xml"):
            return DummyResponse(self.rss_text)
        return DummyResponse(self.html_text)

    def post(self, url, json=None, timeout=None, **kwargs):  # noqa: ANN001
        self.sent_payloads.append({"url": str(url), "json": json})
        return DummyResponse("", 204)


class RateLimitedSessionMock(SessionMock):
    def __init__(self, rss_text: str, html_text: str, fail_count: int):
        super().__init__(rss_text, html_text)
        self.remaining_failures = fail_count

    def post(self, url, json=None, timeout=None, **kwargs):  # noqa: ANN001
        self.sent_payloads.append({"url": str(url), "json": json})
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            return DummyResponse("", 429, json_data={"retry_after": 0})
        return DummyResponse("", 204)


class AlwaysFailingAlertSessionMock(SessionMock):
    def post(self, url, json=None, timeout=None, **kwargs):  # noqa: ANN001
        self.sent_payloads.append({"url": str(url), "json": json})
        return DummyResponse("", 429, json_data={"retry_after": 0})


def _rss() -> str:
    return """<rss version='2.0'><channel><item><title>1BR laundry $3200</title><link>https://example.com/1</link><description>Mission District</description><guid>1</guid></item></channel></rss>"""


def _html() -> str:
    return """<div class='listing' data-id='x2'><a href='https://example.com/2'><span class='title'>2BR laundry</span></a><span class='price'>$3500</span><span class='beds'>2 bed</span><span class='location'>Mission</span><p class='summary'>parking included</p></div>"""


def test_poll_new_only_alert_behavior(app_config):
    app_config.discord.webhook_url = "https://discord.example.com/hook"
    repo = SQLiteRepository(app_config.db_path)
    session = SessionMock(_rss(), _html())
    pipeline = PollPipeline(app_config, repo, session=session)

    first = pipeline.run_cycle(alerting_enabled=True)
    assert first["first_run_seed"] is True
    assert len(session.sent_payloads) == 0

    second = pipeline.run_cycle(alerting_enabled=True)
    assert second["alerted"] == 0

    repo.close()


def test_poll_dual_stream_alerts(app_config):
    app_config.discord.strict_webhook_url = "https://discord.example.com/strict"
    app_config.discord.broad_webhook_url = "https://discord.example.com/broad"
    app_config.filters.neighborhoods = []
    app_config.filters.include_keywords = []
    repo = SQLiteRepository(app_config.db_path)
    session = SessionMock(_rss(), _html())
    pipeline = PollPipeline(app_config, repo, session=session)

    # seed baseline without notifications
    pipeline.run_cycle(alerting_enabled=False)

    # introduce one strict+geo matching new listing
    session.rss_text = """<rss version='2.0'><channel><item><title>1BR laundry $3200</title><link>https://example.com/1</link><description>Mission District</description><guid>1</guid></item><item><title>1BR laundry $3100</title><link>https://example.com/3</link><description>Mission District</description><guid>3</guid></item></channel></rss>"""
    second = pipeline.run_cycle(alerting_enabled=True)

    assert second["alerted"] == 2
    urls = [item["url"] for item in session.sent_payloads]
    assert "https://discord.example.com/broad" in urls
    assert "https://discord.example.com/strict" in urls

    repo.close()


def test_poll_logs_source_progress(app_config, caplog):
    repo = SQLiteRepository(app_config.db_path)
    session = SessionMock(_rss(), _html())
    pipeline = PollPipeline(app_config, repo, session=session)

    with caplog.at_level(logging.INFO, logger="sf_apartment_aggregator"):
        pipeline.run_cycle(alerting_enabled=False)

    started_sources = [record.data["source"] for record in caplog.records if getattr(record, "event", None) == "source_started"]
    finished_sources = [record.data["source"] for record in caplog.records if getattr(record, "event", None) == "source_finished"]

    assert started_sources == ["craigslist", "greystar"]
    assert finished_sources == ["craigslist", "greystar"]

    repo.close()


def test_notifier_retries_rate_limited_alerts(app_config):
    app_config.discord.webhook_url = "https://discord.example.com/hook"
    app_config.filters.neighborhoods = []
    app_config.filters.include_keywords = []
    repo = SQLiteRepository(app_config.db_path)
    session = RateLimitedSessionMock(_rss(), _html(), fail_count=1)
    pipeline = PollPipeline(app_config, repo, session=session)

    pipeline.run_cycle(alerting_enabled=False)
    session.rss_text = """<rss version='2.0'><channel><item><title>1BR laundry $3200</title><link>https://example.com/1</link><description>Mission District</description><guid>1</guid></item><item><title>1BR laundry $3100</title><link>https://example.com/3</link><description>Mission District</description><guid>3</guid></item></channel></rss>"""

    with patch("sf_apartment_aggregator.notifier.time.sleep", return_value=None):
        summary = pipeline.run_cycle(alerting_enabled=True)

    assert summary["alerted"] == 1
    assert len(session.sent_payloads) >= 2
    repo.close()


def test_alert_failures_do_not_mark_source_parse_failed(app_config):
    app_config.discord.webhook_url = "https://discord.example.com/hook"
    app_config.filters.neighborhoods = []
    app_config.filters.include_keywords = []
    repo = SQLiteRepository(app_config.db_path)
    session = AlwaysFailingAlertSessionMock(_rss(), _html())
    pipeline = PollPipeline(app_config, repo, session=session)

    pipeline.run_cycle(alerting_enabled=False)
    session.rss_text = """<rss version='2.0'><channel><item><title>1BR laundry $3200</title><link>https://example.com/1</link><description>Mission District</description><guid>1</guid></item><item><title>1BR laundry $3100</title><link>https://example.com/3</link><description>Mission District</description><guid>3</guid></item></channel></rss>"""

    with patch("sf_apartment_aggregator.notifier.time.sleep", return_value=None):
        summary = pipeline.run_cycle(alerting_enabled=True)

    craigslist_result = next(result for result in summary["source_results"] if result["source"] == "craigslist")
    assert craigslist_result["success"] is True
    assert craigslist_result["matched_count"] == 2
    assert craigslist_result["alerted_count"] == 0
    assert "strict:" in craigslist_result["error_message"]
    repo.close()


def test_source_rerun_guard_skips_recent_craigslist_runs(app_config):
    app_config.sources[0].min_poll_interval_minutes = 15
    app_config.sources[0].enrich_detail_pages = False
    repo = SQLiteRepository(app_config.db_path)
    session = SessionMock(_rss(), _html())
    pipeline = PollPipeline(app_config, repo, session=session)

    first = pipeline.run_cycle(alerting_enabled=False)
    second = pipeline.run_cycle(alerting_enabled=False)

    first_craigslist = next(result for result in first["source_results"] if result["source"] == "craigslist")
    second_craigslist = next(result for result in second["source_results"] if result["source"] == "craigslist")
    assert first_craigslist["parsed_count"] == 1
    assert second_craigslist["parsed_count"] == 0
    assert second_craigslist["error_message"] == "source_rate_limited_recent_run"
    repo.close()


def test_source_block_cooldown_skips_craigslist_after_block(app_config):
    app_config.sources[0].min_poll_interval_minutes = None
    app_config.sources[0].cooldown_on_block_minutes = 720
    app_config.sources[0].enrich_detail_pages = False
    repo = SQLiteRepository(app_config.db_path)
    session = SessionMock(_rss(), _html())
    pipeline = PollPipeline(app_config, repo, session=session)

    repo.conn.execute(
        """
        INSERT INTO source_runs(
          source, source_type, started_at, finished_at, success, fetched_count, parsed_count,
          new_count, matched_count, alerted_count, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("craigslist", "rss", "2026-05-24T00:00:00+00:00", utcnow().isoformat(), 0, 0, 0, 0, 0, 0, "craigslist_blocked_page"),
    )
    repo.conn.commit()

    summary = pipeline.run_cycle(alerting_enabled=False)

    craigslist_result = next(result for result in summary["source_results"] if result["source"] == "craigslist")
    assert craigslist_result["parsed_count"] == 0
    assert craigslist_result["error_message"] == "source_cooldown_after_block"
    repo.close()
