"""Manual login flow.

Barchart's login form (fields, anti-bot checks, 2FA) can't be verified from
this environment, so rather than scripting form-fill (which would be brittle
and could trip anti-automation checks), this opens a real, visible browser
window and lets you log in by hand. Once you confirm you're logged in, the
session cookies are saved to disk and reused by the scraper headlessly, so
you only need to do this occasionally (whenever the session expires).
"""

import asyncio
import base64
import pathlib

from playwright.async_api import async_playwright

from . import config


def bootstrap_storage_state_from_env() -> None:
    """Write a base64-encoded session (BARCHART_STORAGE_STATE_B64) to disk.

    For deployments where interactive login isn't possible (e.g. a cloud
    container): run `login` locally to produce storage_state.json, base64
    it, and set that as this env var. No-op if the file already exists or
    the env var isn't set.
    """
    import os

    if pathlib.Path(config.STORAGE_STATE_PATH).exists():
        return
    b64 = os.getenv("BARCHART_STORAGE_STATE_B64", "").strip()
    if not b64:
        return
    pathlib.Path(config.STORAGE_STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(config.STORAGE_STATE_PATH).write_bytes(base64.b64decode(b64))


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
