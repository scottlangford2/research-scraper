"""
USAspending.gov API scraper for recent federal awards.

Queries the USAspending.gov spending-by-award API for recent contracts
and grants matching research keywords. No authentication required.
"""

import time
from datetime import datetime, timedelta

import requests

from config import USASPENDING_LOOKBACK_DAYS, REQUEST_TIMEOUT, POLITE_DELAY, log
from filters import KEYWORDS

# Use the first 30 keywords for broad coverage without hitting API limits
_SEARCH_KEYWORDS = list(KEYWORDS[:30])


def scrape_usaspending() -> list[dict]:
    """Query USAspending.gov API for recent federal awards."""
    log.info("Querying USAspending.gov API...")
    rfps: list[dict] = []

    cutoff = (datetime.now() - timedelta(days=USASPENDING_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    for award_type in [["A", "B", "C", "D"], ["02", "03", "04", "05"]]:
        # First group = contracts; Second group = grants
        label = "Contracts" if "A" in award_type else "Grants"
        try:
            resp = requests.post(
                "https://api.usaspending.gov/api/v2/search/spending_by_award/",
                json={
                    "filters": {
                        "award_type_codes": award_type,
                        "time_period": [{"start_date": cutoff, "end_date": today}],
                        "keywords": _SEARCH_KEYWORDS,
                    },
                    "fields": [
                        "Award ID", "Recipient Name", "Description",
                        "Start Date", "End Date", "Award Amount",
                        "Awarding Agency", "generated_internal_id",
                    ],
                    "limit": 100,
                    "page": 1,
                    "sort": "Award Amount",
                    "order": "desc",
                },
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            for result in data.get("results", []):
                award_id = result.get("Award ID", result.get("generated_internal_id", ""))
                amount = str(result.get("Award Amount", "")) if result.get("Award Amount") else ""
                internal_id = result.get("generated_internal_id", "")

                rfps.append({
                    "state": "Federal",
                    "source": f"USAspending ({label})",
                    "id": str(award_id),
                    "title": result.get("Description", ""),
                    "agency": result.get("Awarding Agency", ""),
                    "status": "Awarded",
                    "posted_date": result.get("Start Date", ""),
                    "close_date": result.get("End Date", ""),
                    "url": f"https://www.usaspending.gov/award/{internal_id}" if internal_id else "",
                    "description": (result.get("Description", "") or "")[:500],
                    "amount": amount,
                })

            time.sleep(POLITE_DELAY)
        except requests.RequestException as e:
            log.error(f"USAspending {label} query failed: {e}")
            continue

    log.info(f"USAspending total: {len(rfps)} recent awards")
    return rfps
