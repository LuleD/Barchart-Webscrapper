import argparse
import asyncio
import logging
import pathlib
import time
from datetime import datetime, timezone

from playwright.async_api import async_playwright

from . import config
from .auth import manual_login
from .scraper import scrape_volatility_greeks
from .series_resolver import SeriesInfo, resolve_one_day_series
from .storage import init_db, save_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("barchart_scraper")


async def _get_series(page) -> SeriesInfo:
    if config.STATIC_SERIES_URL:
        return SeriesInfo(
            symbol="STATIC", url=config.STATIC_SERIES_URL, expiration_date=None, days_to_expiration=None
        )
    resolved = await resolve_one_day_series(page, config.UNDERLYING_SYMBOL)
    if resolved:
        return resolved
    raise RuntimeError(
        "Could not automatically resolve the current 1-day-to-expiration option "
        "series. As a temporary workaround, set BARCHART_STATIC_SERIES_URL in "
        ".env to a specific volatility-greeks URL, and run with --debug to "
        "capture page HTML/screenshot for fixing series_resolver.py."
    )


async def _dump_debug(page) -> None:
    pathlib.Path(config.DEBUG_DIR).mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    html_path = pathlib.Path(config.DEBUG_DIR) / f"page_{ts}.html"
    png_path = pathlib.Path(config.DEBUG_DIR) / f"page_{ts}.png"
    html_path.write_text(await page.content())
    await page.screenshot(path=str(png_path), full_page=True)
    log.warning("Saved debug HTML to %s and screenshot to %s", html_path, png_path)


async def run_once(page, debug: bool = False) -> None:
    series = await _get_series(page)
    url = series.url
    if "futuresOptionsView" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}futuresOptionsView=split"

    try:
        rows, expiration_info = await scrape_volatility_greeks(page, url)
    except Exception:
        if debug:
            await _dump_debug(page)
        raise

    dte = expiration_info["daysToExpiration"] if expiration_info else series.days_to_expiration
    exp_date = expiration_info["expirationDate"] if expiration_info else series.expiration_date

    saved = save_snapshot(
        rows=rows,
        underlying_symbol=config.UNDERLYING_SYMBOL,
        option_series_symbol=series.symbol,
        expiration_date=exp_date,
        days_to_expiration=dte,
        db_path=config.DB_PATH,
    )
    log.info("Saved %d rows for series=%s dte=%s expiration=%s", saved, series.symbol, dte, exp_date)


async def _run(command: str, debug: bool) -> None:
    init_db()

    storage_state = (
        config.STORAGE_STATE_PATH if pathlib.Path(config.STORAGE_STATE_PATH).exists() else None
    )
    if storage_state is None:
        log.warning(
            "No saved login session found at %s. If the page requires "
            "authentication, run `python -m barchart_scraper.cli login` first.",
            config.STORAGE_STATE_PATH,
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.HEADLESS)
        context = await browser.new_context(storage_state=storage_state)
        page = await context.new_page()

        try:
            if command == "once":
                await run_once(page, debug=debug)
            else:
                log.info("Starting polling loop every %ds (Ctrl+C to stop)", config.POLL_INTERVAL_SECONDS)
                while True:
                    cycle_start = time.monotonic()
                    try:
                        await run_once(page, debug=debug)
                    except Exception:
                        log.exception("Scrape cycle failed; will retry next cycle")
                    elapsed = time.monotonic() - cycle_start
                    await asyncio.sleep(max(0.0, config.POLL_INTERVAL_SECONDS - elapsed))
        finally:
            await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Barchart options volatility & greeks scraper")
    parser.add_argument(
        "--debug", action="store_true", help="Dump page HTML/screenshot on failure to data/debug/"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="Open a browser to log in manually and save the session")
    sub.add_parser("once", help="Run a single scrape and exit")
    sub.add_parser("run", help="Run continuously, polling every POLL_INTERVAL_SECONDS")

    args = parser.parse_args()

    if args.command == "login":
        asyncio.run(manual_login())
    else:
        asyncio.run(_run(args.command, args.debug))


if __name__ == "__main__":
    main()
