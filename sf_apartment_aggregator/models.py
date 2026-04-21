from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class NormalizedListing:
    source: str
    source_type: str
    listing_url: str
    canonical_url: str
    external_id: str | None
    title: str
    price: int | None
    beds: float | None
    location_text: str
    neighborhood: str | None
    summary: str
    scraped_at: datetime
    published_at: datetime | None


@dataclass(slots=True)
class AlertPayload:
    title: str
    url: str
    description: str
    fields: list[dict[str, str]]
    timestamp: str

    def as_discord_embed(self) -> dict[str, Any]:
        return {
            "embeds": [
                {
                    "title": self.title,
                    "url": self.url,
                    "description": self.description,
                    "fields": self.fields,
                    "timestamp": self.timestamp,
                }
            ]
        }


@dataclass(slots=True)
class SourceRunResult:
    source: str
    source_type: str
    started_at: datetime
    finished_at: datetime
    success: bool
    fetched_count: int
    parsed_count: int
    new_count: int
    matched_count: int
    alerted_count: int
    error_message: str | None = None
