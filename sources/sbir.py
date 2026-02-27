"""
SBIR.gov API scraper for open solicitations.

Queries the SBIR.gov public API for open SBIR/STTR solicitations across
all 11 federal agencies. No authentication required.
"""

import time

import requests

from config import SBIR_MAX_PAGES, REQUEST_TIMEOUT, POLITE_DELAY, log


def scrape_sbir() -> list[dict]:
    """Query SBIR.gov API for open solicitations."""
    log.info("Querying SBIR.gov API...")
    rfps: list[dict] = []

    try:
        page = 0
        while True:
            # SBIR API is aggressive with rate limiting; retry with backoff
            resp = None
            for attempt in range(3):
                try:
                    resp = requests.get(
                        "https://api.www.sbir.gov/public/api/solicitations",
                        params={"keyword": "", "open": 1, "rows": 50, "start": page * 50},
                        timeout=REQUEST_TIMEOUT,
                    )
                    if resp.status_code == 429:
                        wait = 5 * (attempt + 1)
                        log.warning(f"SBIR.gov 429 rate limit, waiting {wait}s (attempt {attempt + 1}/3)")
                        time.sleep(wait)
                        continue
                    resp.raise_for_status()
                    break
                except requests.RequestException:
                    if attempt == 2:
                        raise
                    time.sleep(3)

            if resp is None or resp.status_code == 429:
                log.warning("SBIR.gov rate limit persists after retries, skipping")
                break

            data = resp.json()
            items = data if isinstance(data, list) else data.get("results", data.get("data", []))
            if not items:
                break

            for item in items:
                sol_id = str(
                    item.get("solicitation_number",
                    item.get("solicitationId",
                    item.get("id", "")))
                )
                title = (item.get("solicitation_title",
                         item.get("solicitationTitle",
                         item.get("title", ""))) or "")
                link = (item.get("sbir_solicitation_link",
                        item.get("sbpiUrl",
                        item.get("url", ""))) or "")
                if not link and sol_id:
                    link = f"https://www.sbir.gov/node/{sol_id}"
                status = item.get("current_status", item.get("status", "Open"))

                rfps.append({
                    "state": "Federal",
                    "source": "SBIR.gov",
                    "id": sol_id,
                    "title": title,
                    "agency": item.get("agency", ""),
                    "status": status or "Open",
                    "posted_date": item.get("open_date", item.get("openDate", item.get("postedDate", ""))),
                    "close_date": item.get("close_date", item.get("closeDate", item.get("deadline", ""))),
                    "url": link,
                    "description": (item.get("sbir_solicitation_agency_url", item.get("description", "")) or "")[:500],
                    "amount": "",
                })

            if len(items) < 50:
                break
            page += 1
            if page >= SBIR_MAX_PAGES:
                break
            time.sleep(POLITE_DELAY)

    except requests.RequestException as e:
        log.error(f"SBIR.gov API failed: {e}")

    log.info(f"SBIR.gov total: {len(rfps)} open solicitations")
    return rfps
