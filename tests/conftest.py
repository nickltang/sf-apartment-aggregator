from __future__ import annotations

from pathlib import Path

import pytest

from sf_apartment_aggregator.config import AppConfig, FilterConfig, SourceConfig


@pytest.fixture()
def temp_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture()
def filter_config() -> FilterConfig:
    return FilterConfig(
        max_price=4000,
        min_beds=1,
        max_beds=3,
        neighborhoods=["Mission"],
        aliases={"Mission": ["Mission District", "The Mission"]},
        include_keywords=["laundry"],
        exclude_keywords=["income restricted"],
    )


@pytest.fixture()
def app_config(temp_db_path: str, filter_config: FilterConfig) -> AppConfig:
    return AppConfig(
        poll_interval_minutes=10,
        active_start_hour=0,
        active_end_hour=0,
        db_path=temp_db_path,
        sources=[
            SourceConfig(name="craigslist", type="rss", url="https://example.com/feed.xml"),
            SourceConfig(
                name="greystar",
                type="html",
                url="https://example.com/greystar",
                listing_selector=".listing",
                title_selector=".title",
                url_selector="a",
                price_selector=".price",
                beds_selector=".beds",
                location_selector=".location",
                summary_selector=".summary",
            ),
        ],
        filters=filter_config,
    )
