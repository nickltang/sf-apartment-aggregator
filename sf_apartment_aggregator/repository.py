from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sf_apartment_aggregator.filters import FilterResult
from sf_apartment_aggregator.models import AlertPayload, NormalizedListing, SourceRunResult


@dataclass(slots=True)
class UpsertOutcome:
    canonical_url: str
    is_new: bool


class SQLiteRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS listings (
              canonical_url TEXT PRIMARY KEY,
              source TEXT NOT NULL,
              source_type TEXT NOT NULL,
              listing_url TEXT NOT NULL,
              external_id TEXT,
              title TEXT NOT NULL,
              price INTEGER,
              beds REAL,
              location_text TEXT NOT NULL,
              neighborhood TEXT,
              summary TEXT NOT NULL,
              scraped_at TEXT NOT NULL,
              published_at TEXT,
              first_seen_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              last_match_status INTEGER NOT NULL DEFAULT 0,
              last_match_reason TEXT NOT NULL DEFAULT 'unknown'
            );

            CREATE TABLE IF NOT EXISTS listing_external_ids (
              source TEXT NOT NULL,
              external_id TEXT NOT NULL,
              canonical_url TEXT NOT NULL,
              PRIMARY KEY (source, external_id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              canonical_url TEXT NOT NULL,
              alert_type TEXT NOT NULL DEFAULT 'strict',
              alerted_at TEXT NOT NULL,
              payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source TEXT NOT NULL,
              source_type TEXT NOT NULL,
              started_at TEXT NOT NULL,
              finished_at TEXT NOT NULL,
              success INTEGER NOT NULL,
              fetched_count INTEGER NOT NULL,
              parsed_count INTEGER NOT NULL,
              new_count INTEGER NOT NULL,
              matched_count INTEGER NOT NULL,
              alerted_count INTEGER NOT NULL,
              error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS parse_errors (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source TEXT NOT NULL,
              url TEXT,
              error_message TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        existing_columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(alerts)").fetchall()
        }
        if "alert_type" not in existing_columns:
            self.conn.execute("ALTER TABLE alerts ADD COLUMN alert_type TEXT NOT NULL DEFAULT 'strict'")
        self.conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_canonical_type ON alerts(canonical_url, alert_type)"
        )
        self.conn.commit()

    def is_first_run(self) -> bool:
        row = self.conn.execute("SELECT COUNT(1) AS c FROM listings").fetchone()
        return bool(row and row["c"] == 0)

    def upsert_listing(self, listing: NormalizedListing, filter_result: FilterResult) -> UpsertOutcome:
        now = listing.scraped_at.isoformat()
        if listing.external_id:
            existing_by_external = self.conn.execute(
                "SELECT canonical_url FROM listing_external_ids WHERE source = ? AND external_id = ?",
                (listing.source, listing.external_id),
            ).fetchone()
            if existing_by_external:
                self.conn.execute(
                    """
                    UPDATE listings SET
                      source = ?, source_type = ?, listing_url = ?, external_id = ?, title = ?, price = ?, beds = ?,
                      location_text = ?, neighborhood = ?, summary = ?, scraped_at = ?, published_at = ?, last_seen_at = ?,
                      last_match_status = ?, last_match_reason = ?
                    WHERE canonical_url = ?
                    """,
                    (
                        listing.source,
                        listing.source_type,
                        listing.listing_url,
                        listing.external_id,
                        listing.title,
                        listing.price,
                        listing.beds,
                        listing.location_text,
                        listing.neighborhood,
                        listing.summary,
                        now,
                        listing.published_at.isoformat() if listing.published_at else None,
                        now,
                        int(filter_result.matched),
                        filter_result.reason,
                        existing_by_external["canonical_url"],
                    ),
                )
                self.conn.commit()
                return UpsertOutcome(existing_by_external["canonical_url"], False)

        existing = self.conn.execute(
            "SELECT canonical_url FROM listings WHERE canonical_url = ?",
            (listing.canonical_url,),
        ).fetchone()
        if existing:
            self.conn.execute(
                """
                UPDATE listings SET
                  source = ?, source_type = ?, listing_url = ?, external_id = ?, title = ?, price = ?, beds = ?,
                  location_text = ?, neighborhood = ?, summary = ?, scraped_at = ?, published_at = ?, last_seen_at = ?,
                  last_match_status = ?, last_match_reason = ?
                WHERE canonical_url = ?
                """,
                (
                    listing.source,
                    listing.source_type,
                    listing.listing_url,
                    listing.external_id,
                    listing.title,
                    listing.price,
                    listing.beds,
                    listing.location_text,
                    listing.neighborhood,
                    listing.summary,
                    now,
                    listing.published_at.isoformat() if listing.published_at else None,
                    now,
                    int(filter_result.matched),
                    filter_result.reason,
                    listing.canonical_url,
                ),
            )
            if listing.external_id:
                self.conn.execute(
                    "INSERT OR REPLACE INTO listing_external_ids(source, external_id, canonical_url) VALUES(?, ?, ?)",
                    (listing.source, listing.external_id, listing.canonical_url),
                )
            self.conn.commit()
            return UpsertOutcome(listing.canonical_url, False)

        self.conn.execute(
            """
            INSERT INTO listings(
              canonical_url, source, source_type, listing_url, external_id, title, price, beds,
              location_text, neighborhood, summary, scraped_at, published_at, first_seen_at, last_seen_at,
              last_match_status, last_match_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                listing.canonical_url,
                listing.source,
                listing.source_type,
                listing.listing_url,
                listing.external_id,
                listing.title,
                listing.price,
                listing.beds,
                listing.location_text,
                listing.neighborhood,
                listing.summary,
                now,
                listing.published_at.isoformat() if listing.published_at else None,
                now,
                now,
                int(filter_result.matched),
                filter_result.reason,
            ),
        )
        if listing.external_id:
            self.conn.execute(
                "INSERT OR REPLACE INTO listing_external_ids(source, external_id, canonical_url) VALUES(?, ?, ?)",
                (listing.source, listing.external_id, listing.canonical_url),
            )
        self.conn.commit()
        return UpsertOutcome(listing.canonical_url, True)

    def has_alert_for(self, canonical_url: str, alert_type: str = "strict") -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM alerts WHERE canonical_url = ? AND alert_type = ? LIMIT 1",
            (canonical_url, alert_type),
        ).fetchone()
        return row is not None

    def record_alert(self, canonical_url: str, payload: AlertPayload, alerted_at: datetime, alert_type: str = "strict") -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO alerts(canonical_url, alert_type, alerted_at, payload_json) VALUES (?, ?, ?, ?)",
            (canonical_url, alert_type, alerted_at.isoformat(), json.dumps(payload.as_discord_embed())),
        )
        self.conn.commit()

    def record_source_run(self, result: SourceRunResult) -> None:
        self.conn.execute(
            """
            INSERT INTO source_runs(
              source, source_type, started_at, finished_at, success, fetched_count, parsed_count,
              new_count, matched_count, alerted_count, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.source,
                result.source_type,
                result.started_at.isoformat(),
                result.finished_at.isoformat(),
                int(result.success),
                result.fetched_count,
                result.parsed_count,
                result.new_count,
                result.matched_count,
                result.alerted_count,
                result.error_message,
            ),
        )
        self.conn.commit()

    def record_parse_error(self, source: str, url: str | None, message: str, created_at: datetime) -> None:
        self.conn.execute(
            "INSERT INTO parse_errors(source, url, error_message, created_at) VALUES (?, ?, ?, ?)",
            (source, url, message, created_at.isoformat()),
        )
        self.conn.commit()

    def get_recent_listings(self, limit: int = 200) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT canonical_url, source, source_type, listing_url, title, price, beds, location_text, neighborhood,
                   summary, last_seen_at, last_match_status, last_match_reason
            FROM listings
            ORDER BY last_seen_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_source_health(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT sr.source,
                   sr.source_type,
                   sr.success,
                   sr.error_message,
                   sr.finished_at,
                   sr.new_count,
                   sr.matched_count,
                   sr.alerted_count
            FROM source_runs sr
            JOIN (
              SELECT source, MAX(id) AS id
              FROM source_runs
              GROUP BY source
            ) latest ON latest.id = sr.id
            ORDER BY sr.source
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def get_alert_history(self, limit: int = 200, alert_type: str | None = None) -> list[dict]:
        if alert_type:
            rows = self.conn.execute(
                """
                SELECT a.id, a.canonical_url, a.alert_type, a.alerted_at, l.title, l.price, l.beds, l.source
                FROM alerts a
                LEFT JOIN listings l ON l.canonical_url = a.canonical_url
                WHERE a.alert_type = ?
                ORDER BY a.alerted_at DESC
                LIMIT ?
                """,
                (alert_type, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT a.id, a.canonical_url, a.alert_type, a.alerted_at, l.title, l.price, l.beds, l.source
                FROM alerts a
                LEFT JOIN listings l ON l.canonical_url = a.canonical_url
                ORDER BY a.alerted_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
