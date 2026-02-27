"""
SAM.gov Federal Opportunities API scraper.

Queries the SAM.gov Get Opportunities API for recent federal solicitations.
Requires SAM_GOV_API_KEY in .env.

API keys expire every 90 days. Regenerate at:
  https://sam.gov → Account Details → Public API Key
"""

import time
from datetime import datetime, timedelta

import requests

from config import (SAM_GOV_API_KEY, SAM_LOOKBACK_DAYS, SAM_CHUNK_DAYS,
                    HISTORICAL_MODE, REQUEST_TIMEOUT, POLITE_DELAY, log)

# SAM.gov has used multiple URL patterns; try both
_API_URLS = [
    "https://api.sam.gov/opportunities/v2/search",
    "https://api.sam.gov/prod/opportunities/v2/search",
]


def _date_chunks(total_days: int, chunk_days: int) -> list[tuple[str, str]]:
    """Generate (from_date, to_date) pairs in MM/DD/YYYY going backwards."""
    now = datetime.now()
    chunks = []
    for start_offset in range(0, total_days, chunk_days):
        end_offset = start_offset
        begin_offset = min(start_offset + chunk_days, total_days)
        from_date = (now - timedelta(days=begin_offset)).strftime("%m/%d/%Y")
        to_date = (now - timedelta(days=end_offset)).strftime("%m/%d/%Y")
        chunks.append((from_date, to_date))
    return chunks


def _find_working_url() -> str | None:
    """Probe each candidate URL with a minimal query to find one that works."""
    test_params = {
        "api_key": SAM_GOV_API_KEY,
        "postedFrom": (datetime.now() - timedelta(days=1)).strftime("%m/%d/%Y"),
        "postedTo": datetime.now().strftime("%m/%d/%Y"),
        "limit": 1,
        "offset": 0,
    }
    for url in _API_URLS:
        try:
            resp = requests.get(url, params=test_params, timeout=30)
            if resp.status_code == 200:
                log.info(f"SAM.gov: using endpoint {url}")
                return url
            log.debug(f"SAM.gov: {url} returned {resp.status_code}")
        except requests.RequestException:
            continue
    return None


def scrape_sam_gov() -> list[dict]:
    if not SAM_GOV_API_KEY:
        log.warning("SAM_GOV_API_KEY not set — skipping SAM.gov")
        return []

    log.info("Querying SAM.gov Opportunities API...")

    base_url = _find_working_url()
    if not base_url:
        log.error(
            "SAM.gov: all API endpoints returned errors. "
            "Your API key may have expired (keys expire every 90 days). "
            "Regenerate at: https://sam.gov → Account Details → Public API Key"
        )
        return []

    rfps: list[dict] = []

    if HISTORICAL_MODE:
        chunks = _date_chunks(SAM_LOOKBACK_DAYS, SAM_CHUNK_DAYS)
    else:
        posted_from = (datetime.now() - timedelta(days=SAM_LOOKBACK_DAYS)).strftime("%m/%d/%Y")
        posted_to = datetime.now().strftime("%m/%d/%Y")
        chunks = [(posted_from, posted_to)]

    limit = 1000

    for chunk_idx, (posted_from, posted_to) in enumerate(chunks):
        if HISTORICAL_MODE:
            log.info(f"  SAM.gov chunk {chunk_idx + 1}/{len(chunks)}: {posted_from} to {posted_to}")
        offset = 0

        while True:
            try:
                params = {
                    "api_key": SAM_GOV_API_KEY,
                    "postedFrom": posted_from,
                    "postedTo": posted_to,
                    "ptype": "o,k,p,r",
                    "limit": limit,
                    "offset": offset,
                }
                resp = requests.get(
                    base_url,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()

                opps = data.get("opportunitiesData", [])
                if not opps:
                    break

                for opp in opps:
                    # Extract dollar amount from award or estimate fields
                    amount = ""
                    award = opp.get("award") or {}
                    if isinstance(award, dict):
                        amount = str(award.get("amount", "")) if award.get("amount") else ""
                    if not amount:
                        for amt_key in ("estimatedValue", "baseAndAllOptionsValue",
                                        "totalEstimatedContractValue", "amount"):
                            val = opp.get(amt_key)
                            if val:
                                amount = str(val)
                                break

                    rfps.append({
                        "state": "Federal",
                        "source": "SAM.gov",
                        "id": opp.get("noticeId", ""),
                        "title": opp.get("title", ""),
                        "agency": opp.get("fullParentPathName", opp.get("department", "")),
                        "status": opp.get("type", ""),
                        "posted_date": opp.get("postedDate", ""),
                        "close_date": opp.get("responseDeadLine", ""),
                        "url": opp.get("uiLink", ""),
                        "description": (opp.get("description", "") or "")[:1000],
                        "amount": amount,
                    })

                total = data.get("totalRecords", 0)
                offset += limit
                if offset >= total:
                    break
                time.sleep(POLITE_DELAY)

            except requests.RequestException as e:
                log.error(f"SAM.gov API query failed: {e}")
                break

        time.sleep(POLITE_DELAY)

    log.info(f"SAM.gov: {len(rfps)} federal opportunities")
    return rfps
