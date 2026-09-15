"""Manual login flow.

Barchart's login form (fields, anti-bot checks, 2FA) can't be verified from
this environment, so rather than scripting form-fill (which would be brittle
and could trip anti-automation checks), this opens a real, visible browser
window and lets you log in by hand. Once you confirm you're logged in, the
session cookies are saved to disk and reused by the scraper headlessly, so
you only need to do this occasionally (whenever the session expires).
"""

import asyncio
import pathlib

from playwright.async_api import async_playwright

from . import config


async def manual_login() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(config.LOGIN_URL)

        print(
            "\nA browser window has opened to the Barchart login page.\n"
            "Log in manually (including any 2FA/CAPTCHA), then come back here.\n"
        )
        input("Once you can see you're logged in, press Enter to save the session... ")

        pathlib.Path(config.STORAGE_STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=config.STORAGE_STATE_PATH)
        print(f"Session saved to {config.STORAGE_STATE_PATH}")

        await browser.close()


def run() -> None:
    asyncio.run(manual_login())


if __name__ == "__main__":
    run()
