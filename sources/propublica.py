"""
ProPublica Nonprofit Explorer API scraper.

Queries the ProPublica Nonprofit Explorer for organizations matching
research-related terms. No authentication required.
"""

import time

import requests

from config import REQUEST_TIMEOUT, POLITE_DELAY, log

_SEARCH_TERMS = [
    "public policy research", "education research",
    "health policy", "community development",
    "workforce development", "climate resilience",
    "nonprofit capacity", "government innovation",
]


def scrape_propublica() -> list[dict]:
    """Query ProPublica Nonprofit Explorer API."""
    log.info("Querying ProPublica Nonprofit Explorer...")
    rfps: list[dict] = []
    seen_eins: set[str] = set()

    for term in _SEARCH_TERMS:
        try:
            resp = requests.get(
                "https://projects.propublica.org/nonprofits/api/v2/search.json",
                params={"q": term, "page": 0},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            for org in data.get("organizations", [])[:20]:
                ein = str(org.get("ein", ""))
                if ein in seen_eins:
                    continue
                seen_eins.add(ein)

                ntee = org.get("ntee_code", "") or ""
                city = org.get("city", "") or ""
                state = org.get("state", "") or ""
                location = f"{city}, {state}" if city else state

                rfps.append({
                    "state": "Federal",
                    "source": "ProPublica Nonprofits",
                    "id": ein,
                    "title": org.get("name", ""),
                    "agency": location,
                    "status": "Active Org",
                    "posted_date": "",
                    "close_date": "",
                    "url": f"https://projects.propublica.org/nonprofits/organizations/{ein}" if ein else "",
                    "description": f"NTEE: {ntee} | Score: {org.get('score', '')}",
                    "amount": "",
                })

            time.sleep(POLITE_DELAY)
        except requests.RequestException as e:
            log.error(f"ProPublica query failed for '{term}': {e}")
            continue

    log.info(f"ProPublica Nonprofits total: {len(rfps)} organizations")
    return rfps
