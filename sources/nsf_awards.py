"""
NSF Awards API scraper for recently funded awards.

Queries the NSF Awards API for recent awards matching policy-related
keywords. No authentication required.
"""

import time
from datetime import datetime, timedelta

import requests

from config import NSF_LOOKBACK_DAYS, REQUEST_TIMEOUT, POLITE_DELAY, log

_POLICY_KEYWORDS = [
    "public policy", "public administration", "economic development",
    "climate resilience", "disaster", "education policy",
    "workforce development", "nonprofit", "social equity",
    "health policy", "transportation", "urban planning",
]


def scrape_nsf_awards() -> list[dict]:
    """Query NSF Awards API for recently started awards."""
    log.info("Querying NSF Awards API...")
    rfps: list[dict] = []
    seen_ids: set[str] = set()

    cutoff = (datetime.now() - timedelta(days=NSF_LOOKBACK_DAYS)).strftime("%m/%d/%Y")

    for kw in _POLICY_KEYWORDS:
        try:
            resp = requests.get(
                "https://api.nsf.gov/services/v1/awards.json",
                params={
                    "keyword": kw,
                    "dateStart": cutoff,
                    "printFields": "id,title,agency,startDate,expDate,estimatedTotalAmt,abstractText,piFirstName,piLastName,awardeeCity,awardeeStateCode",
                    "offset": 1,
                    "rpp": 100,
                },
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            for award in data.get("response", {}).get("award", []):
                award_id = award.get("id", "")
                if award_id in seen_ids:
                    continue
                seen_ids.add(award_id)

                amount = str(award.get("estimatedTotalAmt", "")) if award.get("estimatedTotalAmt") else ""

                rfps.append({
                    "state": "Federal",
                    "source": "NSF Awards",
                    "id": award_id,
                    "title": award.get("title", ""),
                    "agency": f"NSF — {award.get('agency', 'NSF')}",
                    "status": "Awarded",
                    "posted_date": award.get("startDate", ""),
                    "close_date": award.get("expDate", ""),
                    "url": f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={award_id}" if award_id else "",
                    "description": (award.get("abstractText", "") or "")[:500],
                    "amount": amount,
                })

            time.sleep(POLITE_DELAY)
        except requests.RequestException as e:
            log.error(f"NSF Awards query failed for '{kw}': {e}")
            continue

    log.info(f"NSF Awards total: {len(rfps)} recent awards")
    return rfps
