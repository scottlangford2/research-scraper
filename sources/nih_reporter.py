"""
NIH RePORTER API scraper for recently funded research projects.

Queries the NIH RePORTER v2 API for newly added projects matching
health-policy-related keywords. No authentication required.
"""

import time
from datetime import datetime

import requests

from config import REQUEST_TIMEOUT, POLITE_DELAY, log

_HEALTH_KEYWORDS = [
    "health policy", "opioid", "substance abuse", "public health",
    "behavioral health", "Medicare", "Medicaid", "health economics",
    "aging", "health services research", "epidemiology",
    "community health", "health disparities",
]


def scrape_nih_reporter() -> list[dict]:
    """Query NIH RePORTER API for recently funded projects."""
    log.info("Querying NIH RePORTER API...")
    rfps: list[dict] = []
    seen_ids: set[str] = set()

    for kw in _HEALTH_KEYWORDS:
        try:
            resp = requests.post(
                "https://api.reporter.nih.gov/v2/projects/search",
                json={
                    "criteria": {
                        "advanced_text_search": {
                            "operator": "and",
                            "search_field": "projecttitle,terms",
                            "search_text": kw,
                        },
                        "fiscal_years": [datetime.now().year],
                        "newly_added_projects_only": True,
                    },
                    "offset": 0,
                    "limit": 50,
                    "sort_field": "project_start_date",
                    "sort_order": "desc",
                },
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            for proj in data.get("results", []):
                proj_num = proj.get("project_num", "")
                if proj_num in seen_ids:
                    continue
                seen_ids.add(proj_num)

                # Extract agency abbreviation
                agency_abbr = "NIH"
                fundings = proj.get("agency_ic_fundings") or []
                if fundings and isinstance(fundings, list):
                    agency_abbr = fundings[0].get("abbreviation", "NIH")

                # PI name(s)
                pi_names = []
                for pi in (proj.get("principal_investigators") or []):
                    name = pi.get("full_name") or ""
                    if not name:
                        first = pi.get("first_name", "")
                        last = pi.get("last_name", "")
                        name = f"{first} {last}".strip()
                    if name:
                        pi_names.append(name)
                pi_name = "; ".join(pi_names[:3])  # cap at 3

                # Organization / institution
                org = proj.get("organization") or {}
                org_name = org.get("org_name", "")
                org_city = org.get("org_city", "")
                org_state = org.get("org_state", "")
                org_loc = f"{org_city}, {org_state}" if org_city else org_state

                # Award amount
                award_amount = ""
                total_cost = proj.get("award_amount") or proj.get("total_cost")
                if total_cost:
                    award_amount = str(total_cost)

                rfps.append({
                    "state": "Federal",
                    "source": "NIH RePORTER",
                    "id": proj_num,
                    "title": proj.get("project_title", ""),
                    "agency": f"NIH / {agency_abbr}",
                    "status": "Active",
                    "posted_date": proj.get("project_start_date", ""),
                    "close_date": proj.get("project_end_date", ""),
                    "url": f"https://reporter.nih.gov/project-details/{proj_num}" if proj_num else "",
                    "description": (proj.get("abstract_text", "") or "")[:500],
                    "amount": award_amount,
                    "recipient": org_name,
                    "recipient_state": org_loc,
                    "pi_name": pi_name,
                })

            time.sleep(POLITE_DELAY)
        except requests.RequestException as e:
            log.error(f"NIH RePORTER query failed for '{kw}': {e}")
            continue

    log.info(f"NIH RePORTER total: {len(rfps)} active projects")
    return rfps
