# Product Spec: SF Apartment Aggregator

## Goal

Build a low-maintenance personal apartment watcher that consolidates fragmented SF rental listings and posts only relevant new matches to Discord in near real time.

## Core Workflow

1. Poll configured data sources on a recurring schedule.
2. Parse RSS feeds and scrape selected property management sites.
3. Normalize listings into a single internal shape.
4. Deduplicate listings, primarily by canonical listing URL.
5. Apply user-defined filters.
6. Send formatted Discord webhook alerts for new matching listings.

## Functional Requirements

- Support Craigslist apartment RSS feeds.
- Support scraping selected SF property management websites.
- Poll roughly every 5 to 10 minutes.
- Normalize listings into a unified record including source, URL, title, price, beds, neighborhood or location, summary, and timestamps.
- Deduplicate listings by URL, with secondary heuristics available when URLs differ but content is obviously identical.
- Allow user-defined filters for price, beds, neighborhoods, and keywords.
- Alert only on new listings that match the active filters.
- Deliver alerts to Discord via webhook with a concise, readable message and direct listing link.

## Open Questions

- Which implementation stack should own scheduling and scraping?
- Which property management sites should be included in v1?
- How should neighborhood matching work: exact list, aliases, or free-text contains?
- How should filter configuration be stored: file-based config, environment variables, or both?
- Should v1 persist state in a local file, SQLite, or another store?

## Non-Goals For V1

- Multi-user accounts or authentication.
- Full browser automation unless a source cannot be scraped otherwise.
- Rich dashboard UI beyond Discord delivery.
- Automatic application submission or contact workflows.
