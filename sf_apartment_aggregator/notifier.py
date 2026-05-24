from __future__ import annotations

from dataclasses import dataclass
import time

import requests

from sf_apartment_aggregator.models import AlertPayload, NormalizedListing


class NotificationError(RuntimeError):
    pass


@dataclass(slots=True)
class DiscordNotifier:
    webhook_url: str | None
    session: requests.Session
    max_retries: int = 3

    def build_payload(self, listing: NormalizedListing, *, stream: str = "strict") -> AlertPayload:
        fields = [
            {"name": "Price", "value": str(listing.price) if listing.price is not None else "Unknown", "inline": True},
            {"name": "Beds", "value": str(listing.beds) if listing.beds is not None else "Unknown", "inline": True},
            {"name": "Source", "value": listing.source, "inline": True},
            {"name": "Location", "value": listing.location_text or "Unknown", "inline": False},
            {"name": "Stream", "value": stream, "inline": True},
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
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            response = self.session.post(target, json=payload.as_discord_embed(), timeout=10)
            if response.status_code < 400:
                return
            if response.status_code == 429 and attempt < self.max_retries:
                retry_after = self._retry_after_seconds(response, attempt)
                time.sleep(retry_after)
                continue
            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                last_error = exc
                break
        raise NotificationError(str(last_error) if last_error else "discord_webhook_send_failed")

    @staticmethod
    def _retry_after_seconds(response: requests.Response, attempt: int) -> float:
        header_value = response.headers.get("Retry-After")
        if header_value:
            try:
                return max(float(header_value), 0.0)
            except ValueError:
                pass
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        retry_after = payload.get("retry_after")
        if isinstance(retry_after, (int, float)):
            # Discord commonly returns milliseconds in JSON payloads.
            if retry_after > 10:
                return max(float(retry_after) / 1000.0, 0.0)
            return max(float(retry_after), 0.0)
        return float(attempt + 1)
