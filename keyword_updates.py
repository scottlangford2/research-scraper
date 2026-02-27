"""
Keyword update overlay from Google Form responses.

Reads the published CSV of form responses, processes add/remove
requests, and provides get_effective_patterns() for email_digest.py.
"""

import csv
import io
import json
import os
from pathlib import Path

import requests

from config import DATA_DIR, log

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OVERRIDES_FILE = DATA_DIR / "keyword_overrides.json"

# Published CSV URL loaded from .env
_CSV_URL = os.getenv("FORM_RESPONSES_CSV_URL", "")

# Google sign-in email -> team_config email (for members whose Google
# account email differs from their university email in team_config.py)
EMAIL_ALIASES: dict[str, str] = {
    # "personal@gmail.com": "university@txstate.edu",
}

# Column indices in the published CSV (0-based).
# Google Forms with "Collect email addresses" enabled produces:
#   Timestamp, Email Address, Q1, Q2, Q3, Q4, Q5
COL_TIMESTAMP = 0
COL_EMAIL = 1
COL_ADD_KW = 4       # "Any keywords or topics you'd like added?"
COL_REMOVE_KW = 5    # "Any keywords or topics you'd like removed?"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_keywords(raw: str) -> list[str]:
    """Parse comma- or newline-separated keyword entries."""
    if not raw or not raw.strip():
        return []
    if "," in raw:
        parts = raw.split(",")
    else:
        parts = raw.split("\n")
    return [p.strip().lower() for p in parts if p.strip()]


def _load_overrides() -> dict:
    """Load the overrides state file."""
    if OVERRIDES_FILE.exists():
        try:
            with open(OVERRIDES_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            log.warning("Corrupt keyword_overrides.json, starting fresh")
    return {"last_processed_timestamp": "", "members": {}}


def _save_overrides(data: dict):
    """Save the overrides state file."""
    with open(OVERRIDES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _resolve_email(form_email: str, team_emails: set[str]) -> str | None:
    """Map a Google sign-in email to a team_config email."""
    email = form_email.strip().lower()
    if email in team_emails:
        return email
    alias_target = EMAIL_ALIASES.get(email, "").lower()
    if alias_target and alias_target in team_emails:
        return alias_target
    return None


# ---------------------------------------------------------------------------
# Core: fetch + process new form responses
# ---------------------------------------------------------------------------

def sync_form_responses(team_members: list[dict]) -> int:
    """Fetch new form responses and update the overrides file.

    Returns the number of new keyword-update responses processed.
    """
    if not _CSV_URL:
        return 0

    team_emails = {m["email"].strip().lower() for m in team_members}

    try:
        resp = requests.get(_CSV_URL, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Failed to fetch form responses CSV: {e}")
        return 0

    reader = csv.reader(io.StringIO(resp.text))
    header = next(reader, None)
    if not header:
        return 0

    overrides = _load_overrides()
    last_ts = overrides.get("last_processed_timestamp", "")
    new_count = 0
    newest_ts = last_ts

    for row in reader:
        if len(row) <= COL_REMOVE_KW:
            continue

        row_ts = row[COL_TIMESTAMP].strip()
        if row_ts <= last_ts:
            continue

        form_email = row[COL_EMAIL].strip() if len(row) > COL_EMAIL else ""
        resolved = _resolve_email(form_email, team_emails)
        if not resolved:
            log.warning(f"Form response from unrecognized email: {form_email}")
            if row_ts > newest_ts:
                newest_ts = row_ts
            continue

        raw_add = row[COL_ADD_KW].strip() if len(row) > COL_ADD_KW else ""
        raw_remove = row[COL_REMOVE_KW].strip() if len(row) > COL_REMOVE_KW else ""
        additions = _parse_keywords(raw_add)
        removals = _parse_keywords(raw_remove)

        if not additions and not removals:
            if row_ts > newest_ts:
                newest_ts = row_ts
            continue

        # Update member overrides
        if resolved not in overrides["members"]:
            overrides["members"][resolved] = {
                "additions": [], "removals": [], "history": [],
            }

        member_data = overrides["members"][resolved]
        existing_adds = set(member_data["additions"])
        existing_rems = set(member_data["removals"])

        for kw in additions:
            existing_adds.add(kw)
            existing_rems.discard(kw)
        for kw in removals:
            existing_rems.add(kw)
            existing_adds.discard(kw)

        member_data["additions"] = sorted(existing_adds)
        member_data["removals"] = sorted(existing_rems)
        member_data["history"].append({
            "timestamp": row_ts,
            "added": additions,
            "removed": removals,
            "raw_add": raw_add,
            "raw_remove": raw_remove,
        })

        new_count += 1
        if row_ts > newest_ts:
            newest_ts = row_ts
        log.info(f"  Keyword update from {resolved}: +{len(additions)} -{len(removals)}")

    overrides["last_processed_timestamp"] = newest_ts
    _save_overrides(overrides)

    if new_count:
        log.info(f"Processed {new_count} keyword update(s) from form")
    return new_count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_effective_patterns(member: dict) -> list[str]:
    """Return merged patterns: base (team_config) + additions - removals."""
    overrides = _load_overrides()
    email = member["email"].strip().lower()
    member_data = overrides.get("members", {}).get(email)

    if not member_data:
        return member["patterns"]

    base = {p.lower() for p in member["patterns"]}
    base |= set(member_data.get("additions", []))
    base -= set(member_data.get("removals", []))

    return sorted(base)
