"""
Socrata SODA API scraper for state open data portals.

Queries Socrata-powered open data sites for procurement/contract data.
Each state is a config entry — adding a new state requires no code changes.
"""

import time
from datetime import datetime, timedelta

import requests

from config import SOCRATA_LOOKBACK_DAYS, REQUEST_TIMEOUT, POLITE_DELAY, log

# ---------------------------------------------------------------------------
# State dataset configurations
# ---------------------------------------------------------------------------

SOCRATA_DATASETS = [
    {
        "state": "TX",
        "label": "Texas Open Data",
        "url": "https://data.texas.gov/resource/svjm-sdfz.json",
        "date_candidates": [
            "award_date", "effective_date", "start_date",
            "contract_award_date", "date", "begin_date",
        ],
        "title_candidates": [
            "contract_description", "description",
            "commodity_description", "contract_name",
        ],
        "id_candidates": [
            "contract_number", "purchase_order_number", "po_number",
        ],
        "agency_candidates": ["agency_name", "agency"],
        "end_date_candidates": ["expiration_date", "end_date"],
    },
    {
        "state": "NY",
        "label": "New York Open Data",
        "url": "https://data.ny.gov/resource/ehig-g5x3.json",
        "date_candidates": [
            "award_date", "begin_date", "renewal_date",
            "fiscal_year_end_date",
        ],
        "title_candidates": [
            "procurement_description", "type_of_procurement",
            "contract_description", "description",
        ],
        "id_candidates": [
            "contract_number", "contract_id", "id",
        ],
        "agency_candidates": ["authority_name", "agency_name", "agency"],
        "end_date_candidates": ["end_date", "expiration_date"],
    },
    {
        "state": "WA",
        "label": "Washington Open Data",
        "url": "https://data.wa.gov/resource/s8d5-pj78.json",
        "date_candidates": [
            "contract_effective_start", "period_of_performance_start",
            "start_date", "effective_date",
        ],
        "title_candidates": [
            "purpose_of_the_contract", "contract_description",
            "description", "title",
        ],
        "id_candidates": [
            "agency_contract_no", "agency_contract_amendment",
            "contract_number", "contract_id",
        ],
        "agency_candidates": ["agency_number_agency_name", "agency_name", "agency"],
        "end_date_candidates": ["end_date", "expiration_date"],
    },
    {
        "state": "MD",
        "label": "Maryland Open Data",
        "url": "https://opendata.maryland.gov/resource/3tu2-tyav.json",
        "date_candidates": [
            "date", "start_date", "award_date",
        ],
        "title_candidates": [
            "short_description", "description", "title",
        ],
        "id_candidates": [
            "bid_number", "contract_id", "id",
        ],
        "agency_candidates": ["organization_name", "agency_name", "agency"],
        "end_date_candidates": ["end_date", "expiration_date"],
    },
    # NOTE: OK, VA, CA removed — no usable Socrata procurement datasets found.
]


def _first_match(record: dict, candidates: list[str]) -> str:
    """Return the value of the first candidate key found in record."""
    for key in candidates:
        val = record.get(key)
        if val:
            return str(val)
    return ""


def _scrape_one_dataset(ds: dict) -> list[dict]:
    """Query a single Socrata dataset and return normalized RFP dicts."""
    state = ds["state"]
    label = ds["label"]
    url = ds["url"]
    rfps: list[dict] = []

    try:
        # Discover columns from a small sample
        resp = requests.get(url, params={"$limit": 5}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        sample = resp.json()
        if not sample:
            log.info(f"  {label}: empty dataset")
            return rfps

        columns = list(sample[0].keys())

        # Find best date column
        date_col = None
        for candidate in ds["date_candidates"]:
            if candidate in columns:
                date_col = candidate
                break

        # Build query
        cutoff = (datetime.now() - timedelta(days=SOCRATA_LOOKBACK_DAYS)).strftime(
            "%Y-%m-%dT00:00:00"
        )
        params: dict = {"$limit": 1000}
        if date_col:
            params["$where"] = f"{date_col} >= '{cutoff}'"
            params["$order"] = f"{date_col} DESC"

        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        for item in data:
            title = _first_match(item, ds["title_candidates"])
            rfps.append({
                "state": state,
                "source": f"{label} (Awarded)",
                "id": _first_match(item, ds["id_candidates"]),
                "title": title,
                "agency": _first_match(item, ds["agency_candidates"]),
                "status": "Awarded",
                "posted_date": item.get(date_col, "") if date_col else "",
                "close_date": _first_match(item, ds["end_date_candidates"]),
                "url": "",
                "description": title[:1000],
            })

    except requests.RequestException as e:
        log.error(f"  {label} query failed: {e}")

    log.info(f"  {label}: {len(rfps)} records")
    return rfps


def scrape_socrata() -> list[dict]:
    """Query all configured Socrata open data portals."""
    log.info(f"Querying {len(SOCRATA_DATASETS)} Socrata open data portals...")
    all_rfps: list[dict] = []

    for ds in SOCRATA_DATASETS:
        results = _scrape_one_dataset(ds)
        all_rfps.extend(results)
        time.sleep(POLITE_DELAY)

    log.info(f"Socrata total: {len(all_rfps)} records across {len(SOCRATA_DATASETS)} states")
    return all_rfps
