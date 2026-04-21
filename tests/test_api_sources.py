from sf_apartment_aggregator.adapters.api_sources import RentSFNowAjaxAdapter
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
