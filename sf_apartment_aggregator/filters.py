from __future__ import annotations

from dataclasses import dataclass

from sf_apartment_aggregator.config import FilterConfig
from sf_apartment_aggregator.models import NormalizedListing


@dataclass(slots=True)
class FilterResult:
    matched: bool
    reason: str


class ListingFilter:
    def __init__(self, config: FilterConfig):
        self.config = config
        self._normalized_alias_lookup = self._build_alias_lookup(config.aliases)

    @staticmethod
    def _build_alias_lookup(aliases: dict[str, list[str]]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for canonical, values in aliases.items():
            canonical_key = canonical.strip().lower()
            lookup[canonical_key] = canonical
            for value in values:
                lookup[value.strip().lower()] = canonical
        return lookup

    def _canonicalize_neighborhood(self, value: str | None) -> str | None:
        if not value:
            return None
        key = value.strip().lower()
        return self._normalized_alias_lookup.get(key, value)

    def evaluate(self, listing: NormalizedListing) -> FilterResult:
        if listing.price is None:
            return FilterResult(False, "missing_price")
        if listing.price > self.config.max_price:
            return FilterResult(False, "price_above_max")

        if listing.beds is None:
            return FilterResult(False, "missing_beds")
        if listing.beds < self.config.min_beds:
            return FilterResult(False, "beds_below_min")
        if self.config.max_beds is not None and listing.beds > self.config.max_beds:
            return FilterResult(False, "beds_above_max")

        if self.config.neighborhoods:
            canonical_neighborhood = self._canonicalize_neighborhood(listing.neighborhood)
            allowed = {self._canonicalize_neighborhood(n) for n in self.config.neighborhoods}
            if canonical_neighborhood not in allowed:
                return FilterResult(False, "neighborhood_excluded")

        haystack = f"{listing.title} {listing.summary} {listing.location_text}".lower()
        include_keywords = [k.lower() for k in self.config.include_keywords]
        exclude_keywords = [k.lower() for k in self.config.exclude_keywords]

        if include_keywords and not any(k in haystack for k in include_keywords):
            return FilterResult(False, "missing_include_keyword")
        if exclude_keywords and any(k in haystack for k in exclude_keywords):
            return FilterResult(False, "contains_exclude_keyword")

        return FilterResult(True, "matched")
