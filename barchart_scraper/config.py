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

DATA_DIR = os.getenv("DATA_DIR", "data")
DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "barchart_options.db"))
STORAGE_STATE_PATH = os.getenv(
    "STORAGE_STATE_PATH", os.path.join(DATA_DIR, "storage_state.json")
)
DEBUG_DIR = os.getenv("DEBUG_DIR", os.path.join(DATA_DIR, "debug"))
