"""SQLite storage for scraped option snapshots.

Each poll writes one row per call/put at every strike, tagged with the poll's
UTC timestamp, so the table accumulates a time series suitable for later
analysis/model training rather than just holding the latest values.
"""

import json
import pathlib
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import List, Optional

from . import config
from .scraper import OptionRow

SCHEMA = """
CREATE TABLE IF NOT EXISTS option_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraped_at TEXT NOT NULL,
    underlying_symbol TEXT NOT NULL,
    option_series_symbol TEXT NOT NULL,
    expiration_date TEXT,
    days_to_expiration INTEGER,
    option_type TEXT NOT NULL,
    strike REAL,
    latest REAL,
    iv REAL,
    delta REAL,
    gamma REAL,
    theta REAL,
    vega REAL,
    iv_skew REAL,
    quote_type TEXT,
    last_trade TEXT,
    raw_row TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_time ON option_snapshots(scraped_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_series
    ON option_snapshots(option_series_symbol, strike, option_type);
"""


def init_db(db_path: str = config.DB_PATH) -> None:
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def save_snapshot(
    rows: List[OptionRow],
    underlying_symbol: str,
    option_series_symbol: str,
    expiration_date: Optional[str],
    days_to_expiration: Optional[int],
    db_path: str = config.DB_PATH,
) -> int:
    scraped_at = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executemany(
            """
            INSERT INTO option_snapshots (
                scraped_at, underlying_symbol, option_series_symbol,
                expiration_date, days_to_expiration, option_type, strike,
                latest, iv, delta, gamma, theta, vega, iv_skew,
                quote_type, last_trade, raw_row
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scraped_at,
                    underlying_symbol,
                    option_series_symbol,
                    expiration_date,
                    days_to_expiration,
                    r.option_type,
                    r.strike,
                    r.latest,
                    r.iv,
                    r.delta,
                    r.gamma,
                    r.theta,
                    r.vega,
                    r.iv_skew,
                    r.quote_type,
                    r.last_trade,
                    json.dumps(r.raw_row),
                )
                for r in rows
            ],
        )
        conn.commit()
        return len(rows)
