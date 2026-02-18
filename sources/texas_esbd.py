"""
Texas ESBD (Electronic State Business Daily) scraper.

Scrapes open solicitations from txsmartbuy.gov/esbd via HTML parsing.
Paginated, 24 results per page.
"""

import time

import requests
from bs4 import BeautifulSoup

from config import ESBD_MAX_PAGES, REQUEST_TIMEOUT, POLITE_DELAY, log


def _esbd_field(container, label: str) -> str:
    """Extract a field value from an ESBD result row by its label text."""
    for strong in container.find_all("strong"):
        if label.lower() in strong.get_text(strip=True).lower():
            parent_p = strong.parent
            if parent_p:
                full = parent_p.get_text(strip=True)
                idx = full.lower().find(label.lower())
                if idx >= 0:
                    after = full[idx + len(label):]
                    return after.lstrip(": ").strip()
    return ""


def scrape_texas_esbd() -> list[dict]:
    log.info("Scraping Texas ESBD...")
    rfps: list[dict] = []

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
    })

    page = 1
    while page <= ESBD_MAX_PAGES:
        try:
            url = f"https://www.txsmartbuy.gov/esbd?page={page}"
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            rows = soup.select(".esbd-result-row")
            if not rows:
                log.info(f"  Page {page}: no results, stopping pagination")
                break

            for row in rows:
                title_div = row.select_one(".esbd-result-title a")
                if not title_div:
                    continue

                title = title_div.get_text(strip=True)
                href = title_div.get("href", "")
                sol_id = _esbd_field(row, "Solicitation ID")
                due_date = _esbd_field(row, "Due Date")
                due_time = _esbd_field(row, "Due Time")
                agency_num = _esbd_field(row, "Agency/Texas SmartBuy Member Number")
                status = _esbd_field(row, "Status")
                posting_date = _esbd_field(row, "Posting Date")

                close_str = f"{due_date} {due_time}".strip() if due_date else ""

                rfps.append({
                    "state": "TX",
                    "source": "TX ESBD",
                    "id": sol_id or href.replace("/esbd/", ""),
                    "title": title,
                    "agency": f"Agency #{agency_num}" if agency_num else "",
                    "status": status,
                    "posted_date": posting_date,
                    "close_date": close_str,
                    "url": f"https://www.txsmartbuy.gov{href}" if href else "",
                    "description": "",
                })

            log.info(f"  Page {page}: {len(rows)} results")
            page += 1
            time.sleep(POLITE_DELAY)

        except requests.RequestException as e:
            log.error(f"ESBD page {page} failed: {e}")
            break

    log.info(f"Texas ESBD total: {len(rfps)} solicitations")
    return rfps
