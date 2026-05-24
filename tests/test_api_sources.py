from sf_apartment_aggregator.adapters.api_sources import GaetaniCollectionAdapter, RentSFNowAjaxAdapter
from sf_apartment_aggregator.config import SourceConfig


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


class DummySession:
    def __init__(self, text: str):
        self._text = text

    def post(self, url, data=None, timeout=None):  # noqa: ANN001
        return DummyResponse(self._text)


class DummyJsonResponse(DummyResponse):
    def __init__(self, payload: dict, status_code: int = 200):
        super().__init__("", status_code=status_code)
        self._payload = payload

    def json(self):
        return self._payload


class DummyJsonSession:
    def __init__(self, payload: dict):
        self._payload = payload

    def get(self, url, timeout=None):  # noqa: ANN001
        return DummyJsonResponse(self._payload)


def test_rentsfnow_adapter_prefers_dollar_price_over_first_numeric_token() -> None:
    source = SourceConfig(name="rentsfnow", type="html", url="https://www.rentsfnow.com/wp-admin/admin-ajax.php")
    html = """
    <div class="apartment searchListingContainer" id="post-12345">
      <a href="/apartments/rental/example-123">
        <h3>Tenderloin</h3>
        <h2>580 O'Farrell #504</h2>
        <p class="apartment-info">Studio \\ 0 Bath \\ $1,095</p>
      </a>
    </div>
    """
    adapter = RentSFNowAjaxAdapter(source, DummySession(html))  # type: ignore[arg-type]
    listings = adapter.fetch()
    assert len(listings) == 1
    assert listings[0].price == 1095
    assert listings[0].beds == 0.0


def test_gaetani_adapter_parses_posted_timestamp() -> None:
    source = SourceConfig(name="gaetani", type="html", url="https://example.com/gaetani.json")
    payload = {
        "values": [
            {
                "data": {
                    "listable_uid": "abc123",
                    "marketing_title": "1BR in Nob Hill",
                    "address_city": "San Francisco",
                    "posted_to_website_at": "2026-05-24T12:34:56Z",
                }
            }
        ]
    }
    adapter = GaetaniCollectionAdapter(source, DummyJsonSession(payload))  # type: ignore[arg-type]
    listings = adapter.fetch()

    assert len(listings) == 1
    assert listings[0].published_at is not None
    assert listings[0].published_at.isoformat() == "2026-05-24T12:34:56+00:00"
