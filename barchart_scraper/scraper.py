"""Scraping logic for a Barchart "Volatility & Greeks" options page.

The table is located generically (by finding a <table> whose header row
contains "Strike", rather than a hardcoded CSS class) so small markup/styling
changes on Barchart's side are less likely to break this. Columns are then
mapped by header text on each side of the Strike column (calls to the left,
puts to the right), matching the "Side-by-Side" layout.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

EXTRACT_TABLE_JS = """
() => {
    const tables = Array.from(document.querySelectorAll('table'));
    for (const table of tables) {
        const headerCells = Array.from(table.querySelectorAll('thead th, thead td'))
            .map(el => el.textContent.trim());
        if (headerCells.some(h => h.toLowerCase() === 'strike')) {
            const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr =>
                Array.from(tr.querySelectorAll('td')).map(td => td.textContent.trim())
            );
            return { headers: headerCells, rows };
        }
    }
    return null;
}
"""

EXPIRATION_TEXT_JS = r"""
() => {
    const match = document.body.innerText.match(
        /(\d+)\s*Days?\s*to\s*expiration\s*on\s*([0-9/]+)/i
    );
    if (!match) return null;
    return { daysToExpiration: parseInt(match[1], 10), expirationDate: match[2] };
}
"""

_WANTED_FIELDS = [
    "latest",
    "iv",
    "delta",
    "gamma",
    "theta",
    "vega",
    "iv skew",
    "type",
    "last trade",
]


def _clean_number(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    t = text.strip()
    if t in ("", "-", "N/A", "n/a", "--", "unch"):
        return None
    m = re.match(r"^[+-]?[\d,]+(\.\d+)?", t)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


@dataclass
class OptionRow:
    option_type: str  # "call" or "put"
    strike: Optional[float]
    latest: Optional[float]
    iv: Optional[float]
    delta: Optional[float]
    gamma: Optional[float]
    theta: Optional[float]
    vega: Optional[float]
    iv_skew: Optional[float]
    quote_type: Optional[str]
    last_trade: Optional[str]
    raw_row: List[str]


def _field_indices(side_headers: List[str], offset: int) -> Dict[str, int]:
    idx: Dict[str, int] = {}
    for name in _WANTED_FIELDS:
        for i, h in enumerate(side_headers):
            if h == name:
                idx[name.replace(" ", "_")] = offset + i
                break
    return idx


def parse_table(headers: List[str], rows: List[List[str]]) -> List[OptionRow]:
    lower_headers = [h.strip().lower() for h in headers]
    try:
        strike_idx = lower_headers.index("strike")
    except ValueError as exc:
        raise ValueError(f"Could not find a 'Strike' column in headers: {headers}") from exc

    call_headers = lower_headers[:strike_idx]
    put_headers = lower_headers[strike_idx + 1 :]
    call_idx = _field_indices(call_headers, 0)
    put_idx = _field_indices(put_headers, strike_idx + 1)

    def build(row: List[str], idx_map: Dict[str, int], option_type: str, strike: Optional[float]) -> Optional[OptionRow]:
        if not idx_map:
            return None

        def get(key: str) -> Optional[str]:
            i = idx_map.get(key)
            return row[i] if i is not None and i < len(row) else None

        return OptionRow(
            option_type=option_type,
            strike=strike,
            latest=_clean_number(get("latest")),
            iv=_clean_number(get("iv")),
            delta=_clean_number(get("delta")),
            gamma=_clean_number(get("gamma")),
            theta=_clean_number(get("theta")),
            vega=_clean_number(get("vega")),
            iv_skew=_clean_number(get("iv_skew")),
            quote_type=get("type"),
            last_trade=get("last_trade"),
            raw_row=row,
        )

    results: List[OptionRow] = []
    for row in rows:
        if len(row) <= strike_idx:
            continue
        strike = _clean_number(row[strike_idx])
        call_row = build(row, call_idx, "call", strike)
        put_row = build(row, put_idx, "put", strike)
        if call_row:
            results.append(call_row)
        if put_row:
            results.append(put_row)

    return results


async def scrape_volatility_greeks(page: Any, url: str) -> Tuple[List[OptionRow], Optional[Dict[str, Any]]]:
    await page.goto(url, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(1500)  # let any client-side rendering settle

    table_data = await page.evaluate(EXTRACT_TABLE_JS)
    if not table_data:
        raise RuntimeError(
            "Could not locate the options table on the page. The page markup may "
            "differ from what this scraper expects, or you may need to log in "
            "(see `python -m barchart_scraper.cli login`)."
        )

    expiration_info = await page.evaluate(EXPIRATION_TEXT_JS)
    rows = parse_table(table_data["headers"], table_data["rows"])
    return rows, expiration_info
