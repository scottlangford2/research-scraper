"""
Grants.gov Federal Grants API scraper.

Queries the Grants.gov search2 API for recently posted grant opportunities.
No authentication required.

Unlike the team scraper (which uses 9 keyword clusters), this uses broad
queries to capture the full population of recent postings for research.
"""

import time

import requests

from config import GRANTS_ROWS_PER_QUERY, HISTORICAL_MODE, REQUEST_TIMEOUT, POLITE_DELAY, log

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

    opp_statuses = "posted|closed|archived" if HISTORICAL_MODE else "posted"

    for query in _BROAD_QUERIES:
        start_record = 0

        while True:
            try:
                resp = requests.post(
                    "https://api.grants.gov/v1/api/search2",
                    json={
                        "keyword": query,
                        "oppStatuses": opp_statuses,
                        "rows": GRANTS_ROWS_PER_QUERY,
                        "startRecordNum": start_record,
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()

                hits = []
                total_count = 0
                if "data" in data and isinstance(data["data"], dict):
                    hits = data["data"].get("oppHits", [])
                    total_count = data["data"].get("hitCount", data["data"].get("totalCount", 0))
                elif "oppHits" in data:
                    hits = data["oppHits"]
                elif isinstance(data, list):
                    hits = data

                if not hits:
                    break

                for hit in hits:
                    opp_id = str(hit.get("id", hit.get("number", hit.get("oppNumber", ""))))
                    if opp_id in seen_ids:
                        continue
                    seen_ids.add(opp_id)

                    # Extract funding amount
                    amount = ""
                    for amt_key in ("awardCeiling", "estimatedTotalProgramFunding",
                                    "awardFloor", "totalFundingAmount",
                                    "estimatedFunding", "ceiling", "amount"):
                        val = hit.get(amt_key)
                        if val:
                            amount = str(val)
                            break

                    rfps.append({
                        "state": "Federal",
                        "source": "Grants.gov",
                        "id": opp_id,
                        "title": hit.get("title", hit.get("oppTitle", "")),
                        "agency": hit.get("agency", hit.get("agencyName", "")),
                        "status": hit.get("oppStatus", "Posted"),
                        "posted_date": hit.get("openDate", hit.get("postDate", "")),
                        "close_date": hit.get("closeDate", hit.get("deadline", "")),
                        "url": f"https://www.grants.gov/search-results-detail/{opp_id}" if opp_id else "",
                        "description": (hit.get("description", hit.get("synopsis", hit.get("title", ""))) or "")[:1000],
                        "amount": amount,
                    })

                log.info(f"  Grants.gov query '{query[:50]}...': {len(hits)} hits (total: {total_count}, fetched: {len(rfps)})")

                start_record += GRANTS_ROWS_PER_QUERY
                if not HISTORICAL_MODE or start_record >= total_count:
                    break
                time.sleep(POLITE_DELAY)

            except requests.RequestException as e:
                log.error(f"Grants.gov query failed: {e}")
                break

    log.info(f"Grants.gov: {len(rfps)} federal grant opportunities")
    return rfps
