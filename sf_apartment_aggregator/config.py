from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl


class SourceConfig(BaseModel):
    name: str
    type: Literal["rss", "html", "browser"]
    url: HttpUrl
    timeout_seconds: int = 10
    retries: int = 1
    min_poll_interval_minutes: int | None = None
    cooldown_on_block_minutes: int | None = None
    enrich_detail_pages: bool = True
    listing_selector: str | None = None
    title_selector: str | None = None
    url_selector: str | None = None
    price_selector: str | None = None
    beds_selector: str | None = None
    location_selector: str | None = None
    summary_selector: str | None = None
    published_selector: str | None = None
    browser_profile_dir: str | None = None
    browser_executable_path: str | None = None
    browser_headless: bool = False
    browser_wait_ms: int = 4000


class FilterConfig(BaseModel):
    min_price: int = 0
    max_price: int
    min_beds: float
    max_beds: float | None = None
    geo_allowlist: list[str] = Field(default_factory=list)
    state_allowlist: list[str] = Field(default_factory=list)
    neighborhoods: list[str] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class DiscordConfig(BaseModel):
    webhook_url: HttpUrl | None = None
    strict_webhook_url: HttpUrl | None = None
    broad_webhook_url: HttpUrl | None = None


class DashboardConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class LoggingConfig(BaseModel):
    level: str = "INFO"


class AppConfig(BaseModel):
    poll_interval_minutes: int = 20
    active_timezone: str = "America/Los_Angeles"
    active_start_hour: int = 8
    active_end_hour: int = 22
    db_path: str = "data/aggregator.db"
    sources: list[SourceConfig]
    filters: FilterConfig
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def _load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    _load_dotenv(config_path.resolve().parent / ".env")
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    discord = raw.setdefault("discord", {})
    env_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    env_strict = os.getenv("DISCORD_STRICT_WEBHOOK_URL")
    env_broad = os.getenv("DISCORD_BROAD_WEBHOOK_URL")

    if env_webhook and not env_strict:
        env_strict = env_webhook
    if env_strict:
        discord["strict_webhook_url"] = env_strict
    if env_broad:
        discord["broad_webhook_url"] = env_broad
    return AppConfig.model_validate(raw)
