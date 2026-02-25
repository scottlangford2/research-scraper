"""
Socrata SODA API scraper for state open data portals.

Queries Socrata-powered open data sites for procurement/contract data.
Each state is a config entry — adding a new state requires no code changes.
"""

import time
from datetime import datetime, timedelta

import requests

from config import SOCRATA_LOOKBACK_DAYS, HISTORICAL_MODE, REQUEST_TIMEOUT, POLITE_DELAY, log

# ---------------------------------------------------------------------------
# State dataset configurations
# ---------------------------------------------------------------------------

SOCRATA_DATASETS = [
    {
        # Actual columns: contract_or_po_2, end_date, pcc_code,
        # po_contract_number, project_name, start_date, total_amount,
        # vendor_name_description
        "state": "TX",
        "label": "Texas Open Data",
        "url": "https://data.texas.gov/resource/svjm-sdfz.json",
        "date_candidates": ["start_date"],
        "title_candidates": ["project_name"],
        "id_candidates": ["po_contract_number"],
        "agency_candidates": ["vendor_name_description"],
        "end_date_candidates": ["end_date"],
        "amount_candidates": ["total_amount"],
    },
    {
        # Actual columns: amount_expended_for_fiscal_year,
        # amount_expended_to_date, authority_name, award_date, award_process,
        # begin_date, contract_amount, current_or_outstanding_balance,
        # exempt_from_publishing, fiscal_year_end_date,
        # number_of_bids_or_proposals_received, nys_or_foreign_business_enterprise,
        # procurement_description, renewal_date, solicited_mwbe, status,
        # type_of_procurement, vendor_*
        "state": "NY",
        "label": "New York Open Data",
        "url": "https://data.ny.gov/resource/ehig-g5x3.json",
        "date_candidates": ["award_date", "begin_date", "renewal_date"],
        "title_candidates": ["procurement_description", "type_of_procurement"],
        "id_candidates": [],  # No contract number in this dataset
        "agency_candidates": ["authority_name"],
        "end_date_candidates": ["fiscal_year_end_date"],
        "amount_candidates": ["contract_amount", "amount_expended_to_date"],
    },
    {
        # Actual columns: agency_contract_amendment, agency_contract_no,
        # agency_number_agency_name, contract_effective_start,
        # contractor_name_search_for, federal_amount, minority_woman_owned,
        # other_amount, period_of_performance_start, procurement_type,
        # purpose_of_the_contract, small_business, state_amount, veteran
        "state": "WA",
        "label": "Washington Open Data",
        "url": "https://data.wa.gov/resource/s8d5-pj78.json",
        "date_candidates": [
            "contract_effective_start", "period_of_performance_start",
        ],
        "title_candidates": ["purpose_of_the_contract", "procurement_type"],
        "id_candidates": ["agency_contract_no", "agency_contract_amendment"],
        "agency_candidates": ["agency_number_agency_name"],
        "end_date_candidates": [],
        "amount_candidates": ["state_amount", "federal_amount", "other_amount"],
    },
    {
        # Actual columns: bid_number, organization_name, short_description
        "state": "MD",
        "label": "Maryland Open Data",
        "url": "https://opendata.maryland.gov/resource/3tu2-tyav.json",
        "date_candidates": [],  # No date columns in this dataset
        "title_candidates": ["short_description"],
        "id_candidates": ["bid_number"],
        "agency_candidates": ["organization_name"],
        "end_date_candidates": [],
        "amount_candidates": [],  # No amount columns
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

        # Build query — paginate to get all records
        page_limit = 50000 if HISTORICAL_MODE else 1000
        offset = 0

        while True:
            params: dict = {"$limit": page_limit, "$offset": offset}
            if SOCRATA_LOOKBACK_DAYS > 0 and date_col:
                cutoff = (datetime.now() - timedelta(days=SOCRATA_LOOKBACK_DAYS)).strftime(
                    "%Y-%m-%dT00:00:00"
                )
                params["$where"] = f"{date_col} >= '{cutoff}'"
            if date_col:
                params["$order"] = f"{date_col} DESC"

            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                break

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
                    "amount": _first_match(item, ds.get("amount_candidates", [])),
                })

            if len(data) < page_limit:
                break  # last page
            offset += page_limit
            log.info(f"    {label}: fetched {len(rfps)} records so far...")
            time.sleep(POLITE_DELAY)

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
