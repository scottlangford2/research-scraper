"""
Grants.gov Federal Grants API scraper.

Queries the Grants.gov search2 API for recently posted grant opportunities.
No authentication required.

Unlike the team scraper (which uses 9 keyword clusters), this uses broad
queries to capture the full population of recent postings for research.
"""

import time

import requests

from config import GRANTS_ROWS_PER_QUERY, REQUEST_TIMEOUT, POLITE_DELAY, log

# Broad query terms — designed to pull a wide cross-section of grants
# without pre-filtering to specific research topics.
_BROAD_QUERIES = [
    "research OR study OR analysis OR evaluation OR assessment",
    "planning OR development OR services OR management OR training",
    "technology OR innovation OR infrastructure OR environment OR health",
]


def scrape_grants_gov() -> list[dict]:
    log.info("Querying Grants.gov API...")
    rfps: list[dict] = []
    seen_ids: set[str] = set()

    for query in _BROAD_QUERIES:
        try:
            resp = requests.post(
                "https://api.grants.gov/v1/api/search2",
                json={
                    "keyword": query,
                    "oppStatuses": "posted",
                    "rows": GRANTS_ROWS_PER_QUERY,
                },
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            hits = []
            if "data" in data and isinstance(data["data"], dict):
                hits = data["data"].get("oppHits", [])
            elif "oppHits" in data:
                hits = data["oppHits"]
            elif isinstance(data, list):
                hits = data

            for hit in hits:
                opp_id = str(hit.get("id", hit.get("number", hit.get("oppNumber", ""))))
                if opp_id in seen_ids:
                    continue
                seen_ids.add(opp_id)

                rfps.append({
                    "state": "Federal",
                    "source": "Grants.gov",
                    "id": opp_id,
                    "title": hit.get("title", hit.get("oppTitle", "")),
                    "agency": hit.get("agency", hit.get("agencyName", "")),
                    "status": "Posted",
                    "posted_date": hit.get("openDate", hit.get("postDate", "")),
                    "close_date": hit.get("closeDate", hit.get("deadline", "")),
                    "url": f"https://www.grants.gov/search-results-detail/{opp_id}" if opp_id else "",
                    "description": (hit.get("description", hit.get("synopsis", hit.get("title", ""))) or "")[:1000],
                })

            log.info(f"  Grants.gov query '{query[:50]}...': {len(hits)} hits")
            time.sleep(POLITE_DELAY)

        except requests.RequestException as e:
            log.error(f"Grants.gov query failed: {e}")
            continue

    log.info(f"Grants.gov: {len(rfps)} federal grant opportunities")
    return rfps
