"""Runs the scraper polling loop and the dashboard web server together in one
process, so a single deployed service can both collect data and display it.
"""

import asyncio
import logging
import os
import pathlib
import time

import uvicorn
from playwright.async_api import async_playwright

from . import config
from .auth import bootstrap_storage_state_from_env
from .cli import run_once
from .storage import init_db
from .webapp import app

log = logging.getLogger("barchart_scraper.serve")


async def _scraper_loop(page) -> None:
    log.info("Starting scrape loop every %ds", config.POLL_INTERVAL_SECONDS)
    while True:
        cycle_start = time.monotonic()
        try:
            await run_once(page, debug=True)
        except Exception:
            log.exception("Scrape cycle failed; will retry next cycle")
        elapsed = time.monotonic() - cycle_start
        await asyncio.sleep(max(0.0, config.POLL_INTERVAL_SECONDS - elapsed))


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db()
    bootstrap_storage_state_from_env()

    storage_state = (
        config.STORAGE_STATE_PATH if pathlib.Path(config.STORAGE_STATE_PATH).exists() else None
    )
    if storage_state is None:
        log.warning(
            "No login session found at %s (and BARCHART_STORAGE_STATE_B64 is not set). "
            "The scraper will likely fail to load authenticated pages until one is provided.",
            config.STORAGE_STATE_PATH,
        )

    port = int(os.environ.get("PORT", "8000"))
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(uv_config)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy=config.playwright_proxy())
        context = await browser.new_context(storage_state=storage_state)
        page = await context.new_page()

        scraper_task = asyncio.create_task(_scraper_loop(page))
        try:
            await server.serve()
        finally:
            scraper_task.cancel()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
