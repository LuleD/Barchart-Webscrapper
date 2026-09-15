# Playwright's official image ships Chromium + all OS-level dependencies
# already installed, matched to the playwright pip version pinned below.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
# Overridden in deployment to point at a persistent volume, e.g. /data.
ENV DATA_DIR=/app/data

CMD ["python", "-m", "barchart_scraper.serve"]
