from __future__ import annotations

from dataclasses import dataclass
import re

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
        self._allowed_neighborhoods: set[str] = {
            canonical
            for canonical in (self._canonicalize_neighborhood(value) for value in config.neighborhoods)
            if canonical
        }
        self._neighborhood_term_lookup = self._build_neighborhood_term_lookup(config.neighborhoods, config.aliases)
        self._allowed_neighborhood_terms = set(self._neighborhood_term_lookup.keys())
        self._geo_allow_terms = {self._normalize_text(v) for v in config.geo_allowlist if self._normalize_text(v)}
        self._state_allowlist = {value.strip().upper() for value in config.state_allowlist if value.strip()}

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    @staticmethod
    def _build_alias_lookup(aliases: dict[str, list[str]]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for canonical, values in aliases.items():
            canonical_key = ListingFilter._normalize_text(canonical)
            lookup[canonical_key] = canonical
            for value in values:
                lookup[ListingFilter._normalize_text(value)] = canonical
        return lookup

    def _canonicalize_neighborhood(self, value: str | None) -> str | None:
        if not value:
            return None
        key = self._normalize_text(value)
        return self._normalized_alias_lookup.get(key, value)

    def _build_neighborhood_term_lookup(
        self, neighborhoods: list[str], aliases: dict[str, list[str]]
    ) -> dict[str, str]:
        term_to_canonical: dict[str, str] = {}
        for neighborhood in neighborhoods:
            canonical = self._canonicalize_neighborhood(neighborhood)
            if not canonical:
                continue
            canonical_term = self._normalize_text(canonical)
            if canonical_term:
                term_to_canonical[canonical_term] = canonical
            for alias in aliases.get(canonical, []):
                normalized_alias = self._normalize_text(alias)
                if normalized_alias:
                    term_to_canonical[normalized_alias] = canonical
        return term_to_canonical

    @staticmethod
    def _contains_term(haystack: str, term: str) -> bool:
        return f" {term} " in f" {haystack} "

    def _combined_listing_text(self, listing: NormalizedListing, *, include_summary: bool = True) -> str:
        summary = listing.summary if include_summary else ""
        return self._normalize_text(
            f"{listing.neighborhood or ''} {listing.location_text or ''} {listing.title or ''} {summary or ''}"
        )

    def infer_neighborhood(self, listing: NormalizedListing) -> str | None:
        haystack = self._combined_listing_text(listing, include_summary=False)
        if not haystack or not self._neighborhood_term_lookup:
            return None
        for term in sorted(self._neighborhood_term_lookup, key=len, reverse=True):
            if self._contains_term(haystack, term):
                return self._neighborhood_term_lookup[term]
        return None

    @staticmethod
    def _extract_state_code(value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r",\s*([A-Z]{2})(?:\b|\s+\d{5}\b)", value)
        if not match:
            return None
        return match.group(1).upper()

    def _evaluate_state_and_geo(self, listing: NormalizedListing) -> FilterResult:
        if self._state_allowlist:
            state = self._extract_state_code(listing.location_text) or self._extract_state_code(listing.neighborhood)
            if state and state not in self._state_allowlist:
                return FilterResult(False, "state_excluded")

        neighborhood_haystack = self._combined_listing_text(listing, include_summary=False)
        if self._geo_allow_terms:
            geo_match = any(self._contains_term(neighborhood_haystack, term) for term in self._geo_allow_terms)
            if not geo_match and self._allowed_neighborhood_terms:
                geo_match = any(
                    self._contains_term(neighborhood_haystack, term) for term in self._allowed_neighborhood_terms
                )
            if not geo_match:
                return FilterResult(False, "geo_excluded")

        return FilterResult(True, "geo_matched")

    def evaluate_broad(self, listing: NormalizedListing) -> FilterResult:
        result = self._evaluate_state_and_geo(listing)
        if not result.matched:
            return result
        return FilterResult(True, "broad_matched")

    def evaluate(self, listing: NormalizedListing) -> FilterResult:
        if listing.price is None:
            return FilterResult(False, "missing_price")
        if listing.price < self.config.min_price:
            return FilterResult(False, "price_below_min")
        if listing.price > self.config.max_price:
            return FilterResult(False, "price_above_max")

        if listing.beds is None:
            return FilterResult(False, "missing_beds")
        if listing.beds < self.config.min_beds:
            return FilterResult(False, "beds_below_min")
        if self.config.max_beds is not None and listing.beds > self.config.max_beds:
            return FilterResult(False, "beds_above_max")

        state_geo_result = self._evaluate_state_and_geo(listing)
        if not state_geo_result.matched:
            return state_geo_result
        neighborhood_haystack = self._combined_listing_text(listing, include_summary=False)

        if self.config.neighborhoods:
            canonical_neighborhood = self._canonicalize_neighborhood(listing.neighborhood)
            if canonical_neighborhood not in self._allowed_neighborhoods:
                matched_term = any(
                    self._contains_term(neighborhood_haystack, term) for term in self._allowed_neighborhood_terms
                )
                if not matched_term:
                    return FilterResult(False, "neighborhood_excluded")

        haystack = f"{listing.title} {listing.summary} {listing.location_text}".lower()
        include_keywords = [k.lower() for k in self.config.include_keywords]
        exclude_keywords = [k.lower() for k in self.config.exclude_keywords]

        if include_keywords and not any(k in haystack for k in include_keywords):
            return FilterResult(False, "missing_include_keyword")
        if exclude_keywords and any(k in haystack for k in exclude_keywords):
            return FilterResult(False, "contains_exclude_keyword")

        return FilterResult(True, "matched")
