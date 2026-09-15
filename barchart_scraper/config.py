import os

from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.barchart.com"
LOGIN_URL = f"{BASE_URL}/login"

# Underlying futures symbol, e.g. GCV26 (Gold Dec 2026).
UNDERLYING_SYMBOL = os.getenv("BARCHART_UNDERLYING", "GCV26")

# Page that lists all option expirations/series for the underlying, used to
# find whichever series currently has 1 day to expiration.
OPTIONS_LIST_URL_TEMPLATE = f"{BASE_URL}/futures/quotes/{{symbol}}/options"

# Optional escape hatch: if set, skip automatic series resolution entirely and
# always scrape this exact volatility-greeks URL. Useful while the automatic
# resolver is being tuned against the real site, or to pin one series.
STATIC_SERIES_URL = os.getenv("BARCHART_STATIC_SERIES_URL", "").strip() or None

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
HEADLESS = os.getenv("HEADLESS", "true").strip().lower() != "false"

# Barchart's WAF/CloudFront blocks requests from cloud-hosting IP ranges
# (confirmed: Railway's IPs get a 403 before the page even loads, regardless
# of a valid logged-in session). Route through a proxy to work around this —
# set PROXY_SERVER (e.g. "http://proxy-host:port") and, if the provider
# requires auth, PROXY_USERNAME / PROXY_PASSWORD. Leave PROXY_SERVER unset to
# connect directly (fine for local runs from a home network).
PROXY_SERVER = os.getenv("PROXY_SERVER", "").strip() or None
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "").strip() or None
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "").strip() or None

DATA_DIR = os.getenv("DATA_DIR", "data")
DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "barchart_options.db"))
STORAGE_STATE_PATH = os.getenv(
    "STORAGE_STATE_PATH", os.path.join(DATA_DIR, "storage_state.json")
)
DEBUG_DIR = os.getenv("DEBUG_DIR", os.path.join(DATA_DIR, "debug"))


def playwright_proxy():
    """Playwright `proxy` kwarg for browser launch, or None for a direct connection."""
    if not PROXY_SERVER:
        return None
    proxy = {"server": PROXY_SERVER}
    if PROXY_USERNAME:
        proxy["username"] = PROXY_USERNAME
    if PROXY_PASSWORD:
        proxy["password"] = PROXY_PASSWORD
    return proxy
