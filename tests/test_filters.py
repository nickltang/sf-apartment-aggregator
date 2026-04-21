from datetime import timezone

from sf_apartment_aggregator.filters import ListingFilter
from sf_apartment_aggregator.models import NormalizedListing
from sf_apartment_aggregator.normalize import utcnow


def _listing(**kwargs):
    base = dict(
        source="x",
        source_type="rss",
        listing_url="https://example.com/1",
        canonical_url="https://example.com/1",
        external_id=None,
        title="Laundry bright unit",
        price=3500,
        beds=1,
        location_text="Mission District",
        neighborhood="Mission District",
        summary="Great laundry",
        scraped_at=utcnow(),
        published_at=utcnow().astimezone(timezone.utc),
    )
    base.update(kwargs)
    return NormalizedListing(**base)


def test_filter_neighborhood_alias_and_keywords(filter_config):
    engine = ListingFilter(filter_config)
    result = engine.evaluate(_listing())
    assert result.matched is True


def test_filter_exclude_keyword(filter_config):
    engine = ListingFilter(filter_config)
    result = engine.evaluate(_listing(summary="income restricted"))
    assert result.matched is False
    assert result.reason == "contains_exclude_keyword"
