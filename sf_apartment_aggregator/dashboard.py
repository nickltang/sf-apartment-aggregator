from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sf_apartment_aggregator.repository import SQLiteRepository


def create_dashboard_app(repository: SQLiteRepository) -> FastAPI:
    app = FastAPI(title="SF Apartment Aggregator Dashboard")

    @app.get("/api/listings")
    def listings(limit: int = 200):
        return {"items": repository.get_recent_listings(limit=limit)}

    @app.get("/api/source-health")
    def source_health():
        return {"items": repository.get_source_health()}

    @app.get("/api/alerts")
    def alerts(limit: int = 200, alert_type: str | None = None):
        return {"items": repository.get_alert_history(limit=limit, alert_type=alert_type)}

    static_dir = Path(__file__).parent / "dashboard_static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index():
        return FileResponse(static_dir / "index.html")

    return app
