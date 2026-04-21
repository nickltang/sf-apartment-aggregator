from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl


class SourceConfig(BaseModel):
    name: str
    type: Literal["rss", "html"]
    url: HttpUrl
    timeout_seconds: int = 10
    retries: int = 1
    listing_selector: str | None = None
    title_selector: str | None = None
    url_selector: str | None = None
    price_selector: str | None = None
    beds_selector: str | None = None
    location_selector: str | None = None
    summary_selector: str | None = None
    published_selector: str | None = None


class FilterConfig(BaseModel):
    max_price: int
    min_beds: float
    max_beds: float | None = None
    neighborhoods: list[str] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class DiscordConfig(BaseModel):
    webhook_url: HttpUrl | None = None


class DashboardConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class LoggingConfig(BaseModel):
    level: str = "INFO"


class AppConfig(BaseModel):
    poll_interval_minutes: int = 10
    db_path: str = "data/aggregator.db"
    sources: list[SourceConfig]
    filters: FilterConfig
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(path: str | Path) -> AppConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return AppConfig.model_validate(raw)
