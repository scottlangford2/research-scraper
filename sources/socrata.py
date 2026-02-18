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
        "url": "https://data.ny.gov/resource/tpvk-ckga.json",
        "date_candidates": [
            "start_date", "contract_start_date", "effective_date",
            "approval_date", "date",
        ],
        "title_candidates": [
            "contract_description", "description", "title", "purpose",
        ],
        "id_candidates": [
            "contract_number", "contract_id", "id",
        ],
        "agency_candidates": ["agency_name", "authority_name", "agency"],
        "end_date_candidates": ["end_date", "contract_end_date", "expiration_date"],
    },
    {
        "state": "OK",
        "label": "Oklahoma Open Data",
        "url": "https://data.ok.gov/resource/j7cn-hx4f.json",
        "date_candidates": [
            "award_date", "effective_date", "start_date", "date",
        ],
        "title_candidates": [
            "contract_description", "description", "title", "commodity_description",
        ],
        "id_candidates": [
            "contract_number", "solicitation_number", "po_number", "id",
        ],
        "agency_candidates": ["agency_name", "agency", "department"],
        "end_date_candidates": ["expiration_date", "end_date"],
    },
    {
        "state": "VA",
        "label": "Virginia Open Data",
        "url": "https://data.virginia.gov/resource/cvsb-386s.json",
        "date_candidates": [
            "award_date", "effective_date", "start_date", "date",
        ],
        "title_candidates": [
            "contract_description", "description", "title",
            "commodity_description", "purpose",
        ],
        "id_candidates": [
            "contract_number", "contract_id", "solicitation_number", "id",
        ],
        "agency_candidates": ["agency_name", "agency", "department", "buyer"],
        "end_date_candidates": ["expiration_date", "end_date", "contract_end_date"],
    },
    {
        "state": "WA",
        "label": "Washington Open Data",
        "url": "https://data.wa.gov/resource/f6w5-q2ck.json",
        "date_candidates": [
            "start_date", "effective_date", "award_date", "date",
        ],
        "title_candidates": [
            "contract_title", "contract_description", "description", "title",
        ],
        "id_candidates": [
            "contract_number", "contract_id", "master_contract_number", "id",
        ],
        "agency_candidates": ["agency_name", "agency", "department"],
        "end_date_candidates": ["end_date", "expiration_date"],
    },
    {
        "state": "MD",
        "label": "Maryland Open Data",
        "url": "https://opendata.maryland.gov/resource/rba4-7ci8.json",
        "date_candidates": [
            "start_date", "award_date", "effective_date", "date",
        ],
        "title_candidates": [
            "description", "contract_description", "title", "purpose",
        ],
        "id_candidates": [
            "contract_id", "contract_number", "id",
        ],
        "agency_candidates": ["agency_name", "agency", "department"],
        "end_date_candidates": ["end_date", "expiration_date"],
    },
    {
        "state": "CA",
        "label": "California Open Data",
        "url": "https://data.ca.gov/resource/35ea-j9pn.json",
        "date_candidates": [
            "purchase_date", "creation_date", "start_date",
            "effective_date", "date",
        ],
        "title_candidates": [
            "item_description", "description", "commodity_description",
            "title", "line_description",
        ],
        "id_candidates": [
            "purchase_order_number", "po_number", "contract_number", "id",
        ],
        "agency_candidates": ["agency_name", "department_name", "agency", "department"],
        "end_date_candidates": ["expiration_date", "end_date"],
    },
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
