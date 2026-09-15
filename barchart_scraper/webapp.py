"""Read-only dashboard showing the latest scraped snapshot.

Reads from the same SQLite database the scraper writes to. Runs in the same
process as the scraper loop (see serve.py) so both share one persistent
volume in the deployed environment, without needing a second service.
"""

import pathlib
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from . import config

app = FastAPI(title="Barchart Options Dashboard")
templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _query_latest() -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    db_path = pathlib.Path(config.DB_PATH)
    if not db_path.exists():
        return None, []

    with sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        latest = conn.execute(
            """
            SELECT scraped_at, underlying_symbol, option_series_symbol,
                   days_to_expiration, expiration_date
            FROM option_snapshots
            ORDER BY scraped_at DESC
            LIMIT 1
            """
        ).fetchone()
        if not latest:
            return None, []

        rows = conn.execute(
            """
            SELECT * FROM option_snapshots
            WHERE scraped_at = ?
            ORDER BY strike ASC
            """,
            (latest["scraped_at"],),
        ).fetchall()
        return _row_to_dict(latest), [_row_to_dict(r) for r in rows]


def _snapshot_count() -> int:
    db_path = pathlib.Path(config.DB_PATH)
    if not db_path.exists():
        return 0
    with sqlite3.connect(config.DB_PATH) as conn:
        return conn.execute(
            "SELECT COUNT(DISTINCT scraped_at) FROM option_snapshots"
        ).fetchone()[0]


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    meta, rows = _query_latest()

    calls_by_strike = {r["strike"]: r for r in rows if r["option_type"] == "call"}
    puts_by_strike = {r["strike"]: r for r in rows if r["option_type"] == "put"}
    strikes = sorted({r["strike"] for r in rows if r["strike"] is not None})

    table_rows = [
        {"strike": s, "call": calls_by_strike.get(s), "put": puts_by_strike.get(s)}
        for s in strikes
    ]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "meta": meta,
            "rows": table_rows,
            "snapshot_count": _snapshot_count(),
        },
    )


@app.get("/api/latest")
async def api_latest() -> JSONResponse:
    meta, rows = _query_latest()
    return JSONResponse({"meta": meta, "rows": rows})


@app.get("/healthz")
async def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/debug", response_class=HTMLResponse)
async def debug_index() -> str:
    """Lists dumped debug HTML/screenshots from failed scrape cycles.

    Temporary diagnostic aid for tuning series_resolver.py / scraper.py
    against the real site without shell access to the deployed container.
    """
    debug_dir = pathlib.Path(config.DEBUG_DIR)
    if not debug_dir.exists():
        return "<p>No debug dumps yet.</p>"
    files = sorted(debug_dir.iterdir(), reverse=True)
    links = "".join(f'<li><a href="/debug/{f.name}">{f.name}</a></li>' for f in files)
    return f"<ul>{links}</ul>" if links else "<p>No debug dumps yet.</p>"


@app.get("/debug/{filename}")
async def debug_file(filename: str) -> FileResponse:
    debug_dir = pathlib.Path(config.DEBUG_DIR).resolve()
    path = (debug_dir / filename).resolve()
    if debug_dir not in path.parents or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path)
