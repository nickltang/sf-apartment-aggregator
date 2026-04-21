from fastapi.testclient import TestClient

from sf_apartment_aggregator.dashboard import create_dashboard_app
from sf_apartment_aggregator.filters import FilterResult
from sf_apartment_aggregator.models import NormalizedListing
from sf_apartment_aggregator.normalize import utcnow
from sf_apartment_aggregator.repository import SQLiteRepository


def test_dashboard_endpoints(temp_db_path: str):
    repo = SQLiteRepository(temp_db_path)
    listing = NormalizedListing(
        source="x",
        source_type="rss",
        listing_url="https://example.com/1",
        canonical_url="https://example.com/1",
        external_id=None,
        title="Test",
        price=3200,
        beds=1,
        location_text="Mission",
        neighborhood="Mission",
        summary="Laundry",
        scraped_at=utcnow(),
        published_at=None,
    )
    repo.upsert_listing(listing, FilterResult(True, "matched"))

    app = create_dashboard_app(repo)
    client = TestClient(app)

    assert client.get("/api/listings").status_code == 200
    assert client.get("/api/source-health").status_code == 200
    assert client.get("/api/alerts").status_code == 200
    repo.close()
