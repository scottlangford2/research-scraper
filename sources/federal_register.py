"""
Federal Register API scraper for funding opportunity notices.

Queries the Federal Register API for recent NOFOs, grant programs, and
cooperative agreements. No authentication required.
"""

import time
from datetime import datetime, timedelta

import requests

from config import FED_REGISTER_LOOKBACK_DAYS, REQUEST_TIMEOUT, POLITE_DELAY, log

_SEARCH_TERMS = [
    "funding opportunity",
    "grant program",
    "cooperative agreement",
    "notice of funding",
    "NOFO",
    "request for proposals",
]


def scrape_federal_register() -> list[dict]:
    """Query Federal Register API for recent funding notices."""
    log.info("Querying Federal Register API...")
    rfps: list[dict] = []
    seen_ids: set[str] = set()

    cutoff = (datetime.now() - timedelta(days=FED_REGISTER_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    for term in _SEARCH_TERMS:
        try:
            # fields[] must be sent as repeated params, not a comma string
            params = [
                ("conditions[type][]", "NOTICE"),
                ("conditions[term]", term),
                ("conditions[publication_date][gte]", cutoff),
                ("per_page", 100),
                ("order", "newest"),
                ("fields[]", "document_number"),
                ("fields[]", "title"),
                ("fields[]", "agencies"),
                ("fields[]", "type"),
                ("fields[]", "publication_date"),
                ("fields[]", "abstract"),
                ("fields[]", "html_url"),
                ("fields[]", "action"),
            ]
            resp = requests.get(
                "https://www.federalregister.gov/api/v1/articles.json",
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            for doc in data.get("results", []):
                doc_id = doc.get("document_number", "")
                if doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)

                agencies = doc.get("agencies", [])
                agency_name = agencies[0].get("name", "") if agencies else ""

                rfps.append({
                    "state": "Federal",
                    "source": "Federal Register",
                    "id": doc_id,
                    "title": doc.get("title", ""),
                    "agency": agency_name,
                    "status": "Notice",
                    "posted_date": doc.get("publication_date", ""),
                    "close_date": "",
                    "url": doc.get("html_url", ""),
                    "description": (doc.get("abstract", "") or "")[:500],
                    "amount": "",
                })

            time.sleep(POLITE_DELAY)
        except requests.RequestException as e:
            log.error(f"Federal Register query failed for '{term}': {e}")
            continue

    log.info(f"Federal Register total: {len(rfps)} funding notices")
    return rfps
