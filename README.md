# SF Apartment Aggregator

V1 apartment watcher for San Francisco rentals.

## Features

- Polls browser, RSS, and HTML sources and normalizes listing records.
- Deduplicates by canonical URL with secondary `source + external_id` key.
- Applies configurable filters (price, beds, neighborhoods, include/exclude keywords).
- Sends one Discord embed per new matching listing.
- Stores listings, source run health, parse errors, and alert history in SQLite.
- Provides a thin read-only dashboard (FastAPI backend + React frontend).

## Installation and Setup

### Prerequisites

- Python 3.11+
- `pip`
- `git`
- Optional: Docker + Docker Compose
- For Craigslist browser mode: Playwright browser runtime (`playwright install chromium`)

### 1. Clone the repository

```bash
git clone https://github.com/nickltang/sf-apartment-aggregator.git
cd sf-apartment-aggregator
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -e '.[dev]'
```

Install Playwright browser binaries:

```bash
playwright install chromium
```

### 4. Configure the app

Edit [`config.yaml`](/Users/nicholastang/workspace/sf-apartment-aggregator/config.yaml):

- `db_path`: where SQLite state is stored
- `poll_interval_minutes`: target polling cadence (default `20`)
- `active_timezone`, `active_start_hour`, `active_end_hour`: run-window controls (daytime-only polling)
- `sources[]`: browser/RSS/HTML sources and selectors
- `filters`: max price, beds, neighborhoods, aliases, keywords
- `discord.webhook_url`: webhook for alerts (optional but needed for Discord notifications)
- `dashboard.host`/`dashboard.port`: local dashboard bind settings

Recommended for secrets: keep webhook URL in `.env` (not committed) and leave `discord.webhook_url` empty in YAML.

```bash
cp .env.example .env
# Edit .env and set:
# DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
# or stream-specific:
# DISCORD_STRICT_WEBHOOK_URL=https://discord.com/api/webhooks/...  # high-intent matches
# DISCORD_BROAD_WEBHOOK_URL=https://discord.com/api/webhooks/...   # broad SF-area new listings
```

For Craigslist browser mode:

- Set `sources[].type: browser`
- Set `sources[].browser_profile_dir` to a persistent local Chrome profile path
- Run one manual poll and complete any Craigslist challenge in the opened browser profile

### 5. Run commands

```bash
sf-apt poll --config config.yaml
sf-apt backfill --config config.yaml
sf-apt dashboard --config config.yaml
```

Command behavior:

- `poll`: one ingestion/filter/alert cycle
- `backfill`: ingestion/filter cycle without alerting historical items
- `dashboard`: runs FastAPI + static React dashboard (read-only)

### 6. Open dashboard

With defaults from `config.yaml`, open:

- `http://127.0.0.1:8000/`

## Scheduling

Use system cron for polling every 20 minutes during daytime:

```cron
*/20 8-21 * * * cd /path/to/sf-apartment-aggregator && /path/to/.venv/bin/sf-apt poll --config config.yaml >> logs/poll.log 2>&1
```

macOS recommended path: `launchd`.

```bash
chmod +x scripts/run_poll.sh scripts/install_launchd_poll.sh
./scripts/install_launchd_poll.sh
launchctl print gui/$(id -u)/com.nickltang.sf-apartment-aggregator.poll
```

To stop/uninstall:

```bash
launchctl bootout gui/$(id -u)/com.nickltang.sf-apartment-aggregator.poll
rm ~/Library/LaunchAgents/com.nickltang.sf-apartment-aggregator.poll.plist
```

## Docker

Build and run both poller + dashboard services:

```bash
docker compose up --build
```

Services in [`docker-compose.yml`](/Users/nicholastang/workspace/sf-apartment-aggregator/docker-compose.yml):

- `aggregator`: runs `sf-apt poll --config config.yaml`
- `dashboard`: runs `sf-apt dashboard --config config.yaml` on port `8000`

## Project Structure

Top-level layout:

- [`pyproject.toml`](/Users/nicholastang/workspace/sf-apartment-aggregator/pyproject.toml): package metadata, dependencies, CLI entrypoint (`sf-apt`)
- [`config.yaml`](/Users/nicholastang/workspace/sf-apartment-aggregator/config.yaml): main runtime config
- [`Dockerfile`](/Users/nicholastang/workspace/sf-apartment-aggregator/Dockerfile), [`docker-compose.yml`](/Users/nicholastang/workspace/sf-apartment-aggregator/docker-compose.yml): container packaging/runtime
- `data/`: SQLite DB location (created at runtime)
- `tests/`: unit/integration tests and parser fixtures

Core application package: [`sf_apartment_aggregator/`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator)

- [`cli.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/cli.py): Typer CLI (`poll`, `backfill`, `dashboard`)
- [`pipeline.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/pipeline.py): end-to-end poll orchestration
- [`config.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/config.py): YAML schema and loading
- [`models.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/models.py): normalized listing and run/result types
- [`filters.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/filters.py): filter evaluation engine and reasons
- [`normalize.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/normalize.py): canonicalization and parsing helpers
- [`repository.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/repository.py): SQLite schema + queries + state transitions
- [`notifier.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/notifier.py): Discord embed payload + webhook client
- [`logging_config.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/logging_config.py): JSON log formatting

Source adapters:

- [`adapters/browser_craigslist.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/adapters/browser_craigslist.py): Craigslist browser-profile ingestion (Playwright)
- [`adapters/rss.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/adapters/rss.py): RSS ingestion
- [`adapters/html_sources.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/adapters/html_sources.py): HTML parsing with CSS selectors

Dashboard:

- [`dashboard.py`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/dashboard.py): API endpoints (`/api/listings`, `/api/source-health`, `/api/alerts`)
- [`dashboard_static/index.html`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/dashboard_static/index.html): static HTML shell
- [`dashboard_static/app.jsx`](/Users/nicholastang/workspace/sf-apartment-aggregator/sf_apartment_aggregator/dashboard_static/app.jsx): thin React UI
