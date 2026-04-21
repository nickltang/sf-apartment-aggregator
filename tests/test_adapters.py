from pathlib import Path

import requests

from sf_apartment_aggregator.adapters.html_sources import HTMLSourceAdapter
from sf_apartment_aggregator.adapters.rss import RSSSourceAdapter
from sf_apartment_aggregator.config import SourceConfig


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


class DummySession(requests.Session):
    def __init__(self, mapping: dict[str, str]):
        super().__init__()
        self.mapping = mapping

    def get(self, url, timeout=None, **kwargs):  # noqa: ANN001
        return DummyResponse(self.mapping[str(url)])


def fixture(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


def test_rss_adapter_parses_entries() -> None:
    source = SourceConfig(name="craigslist", type="rss", url="https://example.com/feed.xml")
    adapter = RSSSourceAdapter(source, DummySession({"https://example.com/feed.xml": fixture("rss.xml")}))
    listings = adapter.fetch()
    assert len(listings) == 1
    assert listings[0].canonical_url == "https://example.com/listing/1"


def test_html_adapters_for_each_source_handle_missing_optionals() -> None:
    for site in ["greystar", "rentsfnow", "gaetani", "jwavro"]:
        source = SourceConfig(
            name=site,
            type="html",
            url=f"https://example.com/{site}",
            listing_selector=".listing",
            title_selector=".title",
            url_selector="a",
            price_selector=".price",
            beds_selector=".beds",
            location_selector=".location",
            summary_selector=".summary",
        )
        adapter = HTMLSourceAdapter(source, DummySession({f"https://example.com/{site}": fixture(f"{site}.html")}))
        listings = adapter.fetch()
        assert len(listings) == 2
        assert listings[1].price is None
        assert listings[1].beds is None
