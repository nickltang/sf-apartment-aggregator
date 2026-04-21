from __future__ import annotations

from dataclasses import dataclass

import requests

from sf_apartment_aggregator.models import AlertPayload, NormalizedListing


@dataclass(slots=True)
class DiscordNotifier:
    webhook_url: str | None
    session: requests.Session

    def build_payload(self, listing: NormalizedListing, *, stream: str = "strict") -> AlertPayload:
        fields = [
            {"name": "Price", "value": str(listing.price) if listing.price is not None else "Unknown", "inline": "true"},
            {"name": "Beds", "value": str(listing.beds) if listing.beds is not None else "Unknown", "inline": "true"},
            {"name": "Source", "value": listing.source, "inline": "true"},
            {"name": "Location", "value": listing.location_text or "Unknown", "inline": "false"},
            {"name": "Stream", "value": stream, "inline": "true"},
        ]
        return AlertPayload(
            title=listing.title,
            url=listing.listing_url,
            description=listing.summary[:300] if listing.summary else "New listing match",
            fields=fields,
            timestamp=listing.scraped_at.isoformat(),
        )

    def send(self, payload: AlertPayload, *, webhook_url: str | None = None) -> None:
        target = webhook_url or self.webhook_url
        if not target:
            return
        response = self.session.post(target, json=payload.as_discord_embed(), timeout=10)
        response.raise_for_status()
