# Barchart Options Scraper

Scrapes the Barchart "Volatility & Greeks" options table for a futures
underlying (e.g. `GCV26` Gold), tracking whichever weekly series currently
has **1 day to expiration**, and appends timestamped snapshots to a local
SQLite database every 5 minutes (configurable) — building a history suitable
for later analysis or model training, not just a latest-values snapshot.

Target page example:
`https://www.barchart.com/futures/quotes/GCV26/volatility-greeks/IY8U26?futuresOptionsView=split`

Uses a real headless browser (Playwright) rather than an API, since Barchart
doesn't publish one for this data — the page is scraped the same way you'd
view it, after logging in.

## Important: this needs to be run/tested on a machine with access to barchart.com

This project was written without live access to barchart.com (the sandbox it
was built in has no route to that host), based on a screenshot of the target
page. The table-parsing logic (`barchart_scraper/scraper.py`) is unit-tested
offline against real transcribed values and should work as-is. Two other
parts are best-effort and will very likely need a quick fix once you run them
against the live site:

- **Login** (`barchart_scraper/auth.py`) — opens a real browser window for
  you to log in manually, so it doesn't depend on guessing form field names.
  Should just work.
- **Series resolution** (`barchart_scraper/series_resolver.py`) — finds
  whichever option series currently has 1 day to expiration by reading
  Barchart's options list page. This page's exact markup couldn't be
  verified from the sandbox, so it may need adjustment.

If series resolution fails, run with `--debug` (see below) to save the page's
HTML and a screenshot to `data/debug/` — share that back and the selectors in
`series_resolver.py` can be corrected precisely. In the meantime, set
`BARCHART_STATIC_SERIES_URL` in `.env` to pin one exact URL as a working
fallback.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# edit .env if you want to change the underlying symbol, poll interval, etc.
```

## Usage

1. **Log in once** (opens a visible browser window):

   ```bash
   python -m barchart_scraper.cli login
   ```

   Log in manually (handles 2FA/CAPTCHA if any), then press Enter in the
   terminal. This saves your session to `data/storage_state.json` (not
   committed to git) so future runs don't need to log in again — until the
   session expires, at which point just re-run this.

2. **Test a single scrape:**

   ```bash
   python -m barchart_scraper.cli --debug once
   ```

   `--debug` saves page HTML/screenshot to `data/debug/` on failure, which is
   the fastest way to diagnose (and report back) anything that doesn't match
   what this scraper expects.

3. **Run continuously**, polling every `POLL_INTERVAL_SECONDS` (default 300):

   ```bash
   python -m barchart_scraper.cli run
   ```

   Runs until you stop it (Ctrl+C). Each cycle's failure is logged and
   retried on the next cycle rather than crashing the whole process.

## Data

SQLite database at `data/barchart_options.db`, table `option_snapshots`: one
row per call/put per strike per poll, with `scraped_at` (UTC), the resolved
`option_series_symbol`, `days_to_expiration`, all the greeks/IV columns, and
a `raw_row` JSON column preserving the original scraped text for every field
(in case a cleanup/parsing choice needs revisiting later without re-scraping).

```sql
sqlite3 data/barchart_options.db "select * from option_snapshots order by scraped_at desc limit 10;"
```

## Dashboard

A read-only dashboard (`barchart_scraper/webapp.py`, FastAPI) shows the most
recent snapshot as a calls/strike/puts table, matching the site's layout.
`barchart_scraper/serve.py` runs the scraper's polling loop and this
dashboard together in a single process, so one deployment does both:

```bash
python -m barchart_scraper.serve
# open http://localhost:8000
```

`GET /api/latest` returns the same data as JSON.

## Deploying (Railway)

The `Dockerfile` builds an image that runs `serve.py`. Two things need to be
set for a cloud deploy, since it can't do the interactive login step:

1. **Persistent storage** — mount a volume (e.g. at `/data`) and set
   `DATA_DIR=/data` so the SQLite DB and session survive restarts/redeploys.
2. **A logged-in session** — run `python -m barchart_scraper.cli login`
   *locally* first (this opens a real browser for you to log in), then:

   ```bash
   base64 -w0 data/storage_state.json   # macOS: base64 -i data/storage_state.json
   ```

   Set the output as the `BARCHART_STORAGE_STATE_B64` environment variable on
   the deployed service. On first boot it's decoded to
   `$DATA_DIR/storage_state.json`; after that the scraper reuses the file on
   the volume directly. Barchart sessions expire eventually — when scraping
   starts failing with what looks like a login/auth issue, repeat this step
   and update the variable.

Without a valid session, the service still runs and serves the dashboard,
but shows "no data yet" — logging in is what actually produces data.

## IP blocking / proxy

Confirmed by deploying: Barchart's CloudFront/WAF blocks requests from
Railway's IPs with a 403 before the page loads at all, regardless of having
a valid logged-in session. This is Barchart blocking cloud-hosting IP
ranges generally, not specific to Railway or to anything in this scraper's
code — the same is likely on most cloud hosts (AWS, GCP, a VPS, etc).

The fix is a proxy that makes requests appear to come from a non-datacenter
IP. Set `PROXY_SERVER` (and `PROXY_USERNAME`/`PROXY_PASSWORD` if the
provider requires auth) — see `.env.example` / the matching Railway
variables. Two tiers to know about:

- **Datacenter proxies** (e.g. Webshare's free tier) are cheap/free but are
  often on the same kind of IP-range blocklists as Railway itself, so they
  may still get a 403 — worth trying first since it costs nothing, but
  don't be surprised if it doesn't work.
- **Residential proxies** (e.g. Bright Data, Smartproxy/Decodo, Oxylabs,
  IPRoyal) route through real ISP-assigned IPs and reliably get past this
  kind of block, but cost money (typically billed per GB).

No proxy is needed running locally on a home network — the login step and
`data/debug/` HTML dump captured earlier both loaded fine from a home IP.

## Tests

Offline, no network/browser required:

```bash
pytest
```
