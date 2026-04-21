from sf_apartment_aggregator.filters import FilterResult
from sf_apartment_aggregator.models import NormalizedListing
from sf_apartment_aggregator.normalize import utcnow
from sf_apartment_aggregator.repository import SQLiteRepository


def _listing(url: str, external_id: str | None = None) -> NormalizedListing:
    return NormalizedListing(
        source="x",
        source_type="rss",
        listing_url=url,
        canonical_url=url,
        external_id=external_id,
        title="t",
        price=3000,
        beds=1,
        location_text="Mission",
        neighborhood="Mission",
        summary="Laundry",
        scraped_at=utcnow(),
        published_at=None,
    )


def test_repository_upsert_and_first_run_seed_behavior(temp_db_path: str) -> None:
    repo = SQLiteRepository(temp_db_path)
    assert repo.is_first_run() is True

    out = repo.upsert_listing(_listing("https://example.com/1"), FilterResult(True, "matched"))
    assert out.is_new is True
    assert repo.is_first_run() is False

    out2 = repo.upsert_listing(_listing("https://example.com/1"), FilterResult(True, "matched"))
    assert out2.is_new is False
    repo.close()


def test_repository_dedupe_secondary_external_id(temp_db_path: str) -> None:
    repo = SQLiteRepository(temp_db_path)
    repo.upsert_listing(_listing("https://example.com/a", external_id="abc"), FilterResult(True, "matched"))
    out = repo.upsert_listing(_listing("https://example.com/b", external_id="abc"), FilterResult(True, "matched"))
    assert out.is_new is False
    assert out.canonical_url == "https://example.com/a"
    repo.close()
