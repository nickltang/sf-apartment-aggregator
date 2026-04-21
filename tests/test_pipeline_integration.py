from __future__ import annotations

import requests

from sf_apartment_aggregator.pipeline import PollPipeline
from sf_apartment_aggregator.repository import SQLiteRepository


class DummyResponse:
    def __init__(self, text: str = "", status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class SessionMock(requests.Session):
    def __init__(self, rss_text: str, html_text: str):
        super().__init__()
        self.rss_text = rss_text
        self.html_text = html_text
        self.sent_payloads = []

    def get(self, url, timeout=None, **kwargs):  # noqa: ANN001
        if str(url).endswith("feed.xml"):
            return DummyResponse(self.rss_text)
        return DummyResponse(self.html_text)

    def post(self, url, json=None, timeout=None, **kwargs):  # noqa: ANN001
        self.sent_payloads.append(json)
        return DummyResponse("", 204)


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
