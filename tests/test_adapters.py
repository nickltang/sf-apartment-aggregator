from pathlib import Path

import requests
import pytest

from sf_apartment_aggregator.adapters.base import AdapterError
from sf_apartment_aggregator.adapters.browser_craigslist import BrowserCraigslistAdapter
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


def test_html_adapter_resolves_relative_listing_urls() -> None:
    source = SourceConfig(
        name="example",
        type="html",
        url="https://example.com/rentals/search",
        listing_selector=".listing",
        title_selector=".title",
        url_selector="a",
    )
    html = """
    <div class="listing">
      <a href="detail/123"><span class="title">Example Listing</span></a>
    </div>
    """
    adapter = HTMLSourceAdapter(source, DummySession({"https://example.com/rentals/search": html}))
    listings = adapter.fetch()

    assert len(listings) == 1
    assert listings[0].listing_url == "https://example.com/rentals/detail/123"


def test_browser_craigslist_parser_extracts_rows() -> None:
    html = """
    <div class="cl-search-result" data-pid="123">
      <a class="cl-app-anchor" href="/sfc/apa/d/san-francisco-sunny-studio/123.html">Sunny Studio</a>
      <span class="priceinfo">$2,950</span>
      <span class="housing">1br</span>
      <span class="location">(mission district)</span>
    </div>
    """
    listings = BrowserCraigslistAdapter.parse_html_document("https://sfbay.craigslist.org/search/sfc/apa", "craigslist_sf", html)
    assert len(listings) == 1
    listing = listings[0]
    assert listing.external_id == "123"
    assert listing.price == 2950
    assert listing.beds == 1.0
    assert "mission" in listing.location_text.lower()


@pytest.mark.parametrize(
    ("html", "expected_error"),
    [
        ("<html><head><title>Craigslist | Human Verification</title></head><body>Verify you are human</body></html>", "craigslist_challenge_page"),
        ("<html><body><p>Your request has been blocked.</p></body></html>", "craigslist_blocked_page"),
        ("<html><body><p>Zero local results found for this search</p></body></html>", "craigslist_no_results"),
        ("<html><body><div id='unexpected-app-shell'></div></body></html>", "craigslist_selector_mismatch"),
    ],
)
def test_browser_craigslist_parser_classifies_empty_pages(html: str, expected_error: str) -> None:
    with pytest.raises(AdapterError, match=expected_error):
        BrowserCraigslistAdapter.parse_html_document(
            "https://sfbay.craigslist.org/search/sfc/apa",
            "craigslist_sf",
            html,
        )
