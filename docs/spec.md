# Technical Spec: SF Apartment Aggregator

## Product Goal

Build a low-maintenance personal apartment watcher that consolidates SF rental listings and sends only relevant new listings to Discord in near real time.

## Phase Plan

### Phase 1 (Core Watcher)

- Source ingestion from Craigslist RSS and selected SF property management sites.
- Normalization into a unified listing model.
- Deduplication and persisted seen/alert state in SQLite.
- Filtering by price, beds, neighborhood aliases, and include/exclude keywords.
- Discord webhook alerts (embed format) for newly matched listings.

### Phase 2 (Dashboard Expansion)

- Expand the local read-only dashboard with richer views and operational metrics.

## V1 Technical Decisions

- Language/runtime: Python.
- Scheduler: system cron invoking a single-run CLI command.
- Poll interval target: every 5-10 minutes (configurable).
- Persistence: SQLite (keep all rows in v1, no prune job).
- Config format: YAML.
- Source strategy: use RSS when available, otherwise HTTP + HTML parsing.
- Browser automation: out of scope for v1.
- Failure handling: best-effort per run (continue when one source fails).
- Deployment: local-first with Docker artifacts (`Dockerfile` and `docker-compose`) for portability.
- Dashboard in v1: thin, read-only local dashboard.

## Source Scope (V1)

### Craigslist (RSS)

- Use Craigslist housing RSS feeds as the primary Craigslist ingestion interface.
- Do not scrape Craigslist listing HTML for index discovery when RSS is available.

### Property Management Sites (HTTP + HTML)

- Greystar: `https://www.greystar.com/`
- RentSFNow: `https://www.rentsfnow.com/`
- Gaetani Real Estate: `https://www.gaetanirealestate.com/`

Each source is implemented as an adapter with source-specific fetch and parse logic mapped into the shared normalized model.

## Architecture

## Runtime Components

1. Scheduler trigger (`cron`) starts `poll`.
2. Source adapters fetch and parse feed/pages.
3. Normalizer maps source data to `NormalizedListing`.
4. Dedupe and state layer upserts records into SQLite.
5. Filter engine evaluates active criteria.
6. Notifier sends Discord embed alerts for newly matched listings.
7. Dashboard/API reads from SQLite for visibility.

## Module Boundaries

- `adapters/`: source-specific fetch and parse.
- `core/normalize.py`: normalization and canonicalization.
- `core/filtering.py`: filter matching logic.
- `core/dedupe.py`: dedupe keys and seen/alert transitions.
- `storage/`: SQLite schema and repository functions.
- `notifiers/discord.py`: webhook payload formatting and delivery.
- `cli/`: `poll`, `backfill`, `dashboard`.
- `dashboard/`: FastAPI API + React read-only UI.

## Data Contracts

## NormalizedListing

Required fields for pipeline processing:

- `source`: stable source key (`craigslist`, `greystar`, `rentsfnow`, `gaetani`)
- `source_type`: `rss` or `html`
- `listing_url`: original listing URL
- `canonical_url`: normalized URL used for primary dedupe
- `title`: listing title/headline
- `price`: numeric monthly rent when parseable
- `beds`: numeric bedroom count when parseable
- `location_text`: source-provided location text
- `summary`: short human-readable listing summary
- `scraped_at`: UTC timestamp when record was captured

Optional fields:

- `external_id`: stable source listing id (if available)
- `published_at`: source publication timestamp (if available)
- `neighborhood`: canonical neighborhood value after mapping (if resolved)

## Dedupe Keys

- Primary dedupe key: `canonical_url`.
- Secondary dedupe key: `(source, external_id)` when `external_id` exists.
- Listing updates may refresh mutable fields (price, summary, beds, last seen) without re-alerting unless listing is new.

## Filter Semantics

- Price: `max_price` required for match when configured.
- Beds: `min_beds` required, optional `max_beds` upper bound.
- Neighborhood matching: canonical neighborhood list with alias mapping.
- Keyword include list: at least one include keyword must match when include list is non-empty.
- Keyword exclude list: any exclude keyword match rejects listing.
- Keyword match scope: `title + summary + location_text`, case-insensitive.

## First-Run and Alert Rules

- First run initializes baseline:
  - Ingest and store listings.
  - Mark currently matching listings as seen without sending alerts.
- Subsequent runs:
  - Alert only when listing is newly discovered and matches filters.
  - One Discord message per listing.
  - No duplicate alerts for the same dedupe key.

## Storage Specification (SQLite)

## Tables

- `listings`
  - normalized listing fields
  - dedupe keys (`canonical_url`, `source`, `external_id`)
  - `first_seen_at`, `last_seen_at`
- `alerts`
  - foreign key to listing identity
  - `alerted_at`
  - webhook delivery status metadata
- `source_runs`
  - run timestamp, source name, success/failure, counts, error summary

## Constraints and Indexes

- Unique index on `canonical_url`.
- Secondary unique index on `(source, external_id)` where `external_id` is not null.
- Indexes on `last_seen_at`, `source`, and `alerted_at` for dashboard reads.

## Configuration Specification (YAML)

Top-level keys:

- `poll_interval_minutes`: integer (recommended 5-10)
- `database_path`: SQLite file path
- `discord`:
  - `webhook_url`
- `filters`:
  - `max_price`
  - `min_beds`
  - `max_beds` (optional)
  - `neighborhoods` (canonical names)
  - `neighborhood_aliases` (map alias -> canonical)
  - `include_keywords`
  - `exclude_keywords`
- `sources`:
  - list of enabled source configs (type, endpoint/start URL, parser settings)
- `dashboard`:
  - host/port and basic UI settings
- `logging`:
  - level and structured JSON output setting

## CLI and Runtime Interfaces

- `poll`: execute one ingestion/filter/alert cycle.
- `backfill`: ingest and refresh baseline state without emitting alerts.
- `dashboard`: run local dashboard services.

All commands return non-zero exit codes on unrecoverable failures. `poll` still attempts all enabled sources before determining final status.

## Discord Notification Contract

- Transport: Discord webhook HTTP POST.
- Format: Discord embed.
- One message per new matching listing.
- Must include: source, price, beds (if known), location/neighborhood, short summary, and direct listing link.

## Dashboard (V1 Thin Read-Only)

- Stack: FastAPI API + React frontend.
- Read-only pages:
  - recent listings
  - recently alerted listings
  - source health/run history
  - latest source errors
- No config editing or write actions through the UI in v1.

## Observability

- Structured JSON logs for each poll cycle:
  - run id, start/end, elapsed time
  - per-source fetched/parsed/matched/alerted counts
  - per-source error details when failures occur
- Persist poll summaries in `source_runs` for dashboard visibility.

## Testing and Acceptance Criteria

## Unit Tests

- URL canonicalization and dedupe key generation.
- Filter logic (price, beds, neighborhood aliases, include/exclude keywords).
- Discord embed payload formatting.

## Parser Fixture Tests

- Craigslist RSS parsing fixture.
- Greystar, RentSFNow, and Gaetani HTML fixtures.
- Missing/partial field scenarios (no beds, no published date, ambiguous price).

## Integration Tests

- End-to-end `poll` with mocked HTTP/RSS and mocked Discord webhook:
  - first run seeds without alerts
  - second run alerts only new matches
  - source-level failure does not block other sources

## Dashboard/API Tests

- Read endpoints return recent listings, alert history, and source run health.
- UI rendering smoke tests for empty and populated states.

## Non-Goals (V1)

- Multi-user auth/accounts.
- Browser automation (Playwright/Selenium) scraping.
- Listing application workflows or outreach automation.
- Write-capable dashboard configuration management.
