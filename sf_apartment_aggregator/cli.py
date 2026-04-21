from __future__ import annotations

import logging
from pathlib import Path

import typer
import uvicorn

from sf_apartment_aggregator.config import load_config
from sf_apartment_aggregator.dashboard import create_dashboard_app
from sf_apartment_aggregator.logging_config import configure_logging
from sf_apartment_aggregator.pipeline import PollPipeline
from sf_apartment_aggregator.repository import SQLiteRepository

app = typer.Typer(help="SF apartment aggregator")
LOGGER = logging.getLogger("sf_apartment_aggregator.cli")


@app.command()
def poll(config: str = typer.Option("config.yaml", help="Path to config YAML")) -> None:
    app_config = load_config(config)
    configure_logging(app_config.logging.level)
    repo = SQLiteRepository(app_config.db_path)
    try:
        summary = PollPipeline(app_config, repo).run_cycle(alerting_enabled=True)
        LOGGER.info("poll_done", extra={"event": "poll_done", "data": summary})
    finally:
        repo.close()


@app.command()
def backfill(config: str = typer.Option("config.yaml", help="Path to config YAML")) -> None:
    app_config = load_config(config)
    configure_logging(app_config.logging.level)
    repo = SQLiteRepository(app_config.db_path)
    try:
        summary = PollPipeline(app_config, repo).run_cycle(alerting_enabled=False)
        LOGGER.info("backfill_done", extra={"event": "backfill_done", "data": summary})
    finally:
        repo.close()


@app.command()
def dashboard(config: str = typer.Option("config.yaml", help="Path to config YAML")) -> None:
    app_config = load_config(config)
    configure_logging(app_config.logging.level)
    repo = SQLiteRepository(app_config.db_path)
    dashboard_app = create_dashboard_app(repo)
    uvicorn.run(dashboard_app, host=app_config.dashboard.host, port=app_config.dashboard.port, log_level="info")


if __name__ == "__main__":
    app()
