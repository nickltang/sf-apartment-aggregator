from datetime import timezone

from sf_apartment_aggregator.config import FilterConfig
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


def test_filter_neighborhood_from_title_or_location_when_field_missing(filter_config):
    engine = ListingFilter(filter_config)
    result = engine.evaluate(
        _listing(
            neighborhood="San Francisco",
            location_text="San Francisco",
            title="Sunny 1BR in Mission District with laundry",
        )
    )
    assert result.matched is True


def test_infer_neighborhood_from_title_alias() -> None:
    cfg = FilterConfig(
        max_price=4000,
        min_beds=1,
        neighborhoods=["Nob Hill"],
        aliases={"Nob Hill": ["Lower Nob Hill"]},
    )
    engine = ListingFilter(cfg)
    inferred = engine.infer_neighborhood(
        _listing(neighborhood="San Francisco", location_text="San Francisco", title="Lower Nob Hill 1BR")
    )
    assert inferred == "Nob Hill"


def test_filter_geo_allowlist_excludes_out_of_region() -> None:
    cfg = FilterConfig(
        max_price=4000,
        min_beds=1,
        geo_allowlist=["San Francisco", "Oakland"],
    )
    engine = ListingFilter(cfg)
    result = engine.evaluate(_listing(location_text="Brooklyn, NY", neighborhood="Brooklyn"))
    assert result.matched is False
    assert result.reason == "geo_excluded"


def test_filter_geo_allowlist_ignores_summary_text_for_geo_match() -> None:
    cfg = FilterConfig(
        max_price=4000,
        min_beds=1,
        geo_allowlist=["San Francisco", "Oakland"],
    )
    engine = ListingFilter(cfg)
    result = engine.evaluate(
        _listing(
            location_text="Bridgeport, CT",
            neighborhood="Bridgeport",
            summary="Housing in San Francisco available now",
        )
    )
    assert result.matched is False
    assert result.reason == "geo_excluded"


def test_filter_state_allowlist_excludes_non_ca_when_present() -> None:
    cfg = FilterConfig(
        max_price=4000,
        min_beds=1,
        state_allowlist=["CA"],
        neighborhoods=["Nob Hill"],
        aliases={"Nob Hill": ["Lower Nob Hill"]},
    )
    engine = ListingFilter(cfg)
    result = engine.evaluate(
        _listing(
            title="Lower Nob Hill 1BR",
            location_text="New York, NY | 123 Main St",
            neighborhood="Nob Hill",
        )
    )
    assert result.matched is False
    assert result.reason == "state_excluded"
