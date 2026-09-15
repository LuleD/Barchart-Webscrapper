"""Finds whichever weekly option series currently has 1 day to expiration.

The target URL you gave (.../volatility-greeks/IY8U26) points at one specific
weekly series, which will itself expire. Since you want to always track
"whatever expires in 1 day" rather than that one fixed series, this resolves
the current series fresh on every poll by reading Barchart's options list page
for the underlying, which lists each expiration with a days-to-expiration
figure, and following the link for the smallest one.

CAVEAT: this page's exact markup could not be verified against the live site
from this sandbox (no network access to barchart.com here). Run
`python -m barchart_scraper.cli --debug once` locally; if resolution fails it
will dump the page HTML/screenshot to data/debug/ so the selectors here can be
corrected precisely. Until then, BARCHART_STATIC_SERIES_URL in .env is a
working fallback that pins one series (see config.py).
"""

import re
from dataclasses import dataclass
from typing import Any, List, Optional

from . import config

BASE_URL = config.BASE_URL


@dataclass
class SeriesInfo:
    symbol: str
    url: str
    expiration_date: Optional[str]
    days_to_expiration: Optional[int]


FIND_EXPIRATION_TABLE_JS = """
() => {
    const tables = Array.from(document.querySelectorAll('table'));
    for (const table of tables) {
        const headers = Array.from(table.querySelectorAll('thead th, thead td'))
            .map(el => el.textContent.trim());
        if (headers.some(h => h.toLowerCase().includes('expiration'))) {
            const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr => ({
                cells: Array.from(tr.querySelectorAll('td')).map(td => td.textContent.trim()),
                links: Array.from(tr.querySelectorAll('a'))
                    .map(a => a.getAttribute('href'))
                    .filter(Boolean),
            }));
            return { headers, rows };
        }
    }
    return null;
}
"""

_DTE_CELL_RE = re.compile(r"^\s*(\d+)\s*(?:days?)?\s*$", re.IGNORECASE)


def _pick_best_row(rows: List[dict]) -> Optional[dict]:
    best_row = None
    best_dte = None
    for row in rows:
        for cell in row["cells"]:
            m = _DTE_CELL_RE.match(cell)
            if m:
                dte = int(m.group(1))
                if dte >= 0 and (best_dte is None or dte < best_dte):
                    best_dte, best_row = dte, row
                break
    if best_row is not None:
        best_row = dict(best_row)
        best_row["_dte"] = best_dte
    return best_row


async def resolve_one_day_series(page: Any, underlying_symbol: str) -> Optional[SeriesInfo]:
    url = config.OPTIONS_LIST_URL_TEMPLATE.format(symbol=underlying_symbol)
    await page.goto(url, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(1000)

    table = await page.evaluate(FIND_EXPIRATION_TABLE_JS)
    if not table:
        return None

    best_row = _pick_best_row(table["rows"])
    if not best_row or not best_row["links"]:
        return None

    href = best_row["links"][0]
    series_url = href if href.startswith("http") else f"{BASE_URL}{href}"

    match = re.search(r"/volatility-greeks/([A-Z0-9]+)", series_url)
    if match:
        series_symbol = match.group(1)
    elif "volatility-greeks" not in series_url:
        series_symbol = "UNKNOWN"
        series_url = f"{series_url.rstrip('/')}/volatility-greeks"
    else:
        series_symbol = "UNKNOWN"

    return SeriesInfo(
        symbol=series_symbol,
        url=series_url,
        expiration_date=None,
        days_to_expiration=best_row.get("_dte"),
    )
