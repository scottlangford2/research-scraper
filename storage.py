"""
Parquet storage and deduplication for the research scraper.
"""

import json
import hashlib
from datetime import datetime, timedelta

import pyarrow as pa
import pyarrow.parquet as pq

from config import PARQUET_FILE, SEEN_FILE, DATA_DIR, HISTORICAL_MODE, log

# ---------------------------------------------------------------------------
# Parquet schema
# ---------------------------------------------------------------------------

RFP_SCHEMA = pa.schema([
    ("rfp_id", pa.string()),
    ("hash", pa.string()),
    ("source", pa.string()),
    ("state", pa.string()),
    ("title", pa.string()),
    ("agency", pa.string()),
    ("status", pa.string()),
    ("posted_date", pa.string()),
    ("close_date", pa.string()),
    ("url", pa.string()),
    ("description", pa.string()),
    ("amount", pa.string()),
    ("recipient", pa.string()),
    ("recipient_state", pa.string()),
    ("pi_name", pa.string()),
    ("keyword_match", pa.bool_()),
    ("matched_keywords", pa.string()),
    ("key_terms", pa.string()),
    ("scrape_date", pa.string()),
    ("scrape_timestamp", pa.timestamp("us")),
])

# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def rfp_hash(rfp: dict) -> str:
    """SHA-256 hash of state-id-title, truncated to 16 hex chars."""
    raw = f"{rfp.get('state', '')}-{rfp.get('id', '')}-{rfp.get('title', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Seen-hash tracking (dedup across runs)
# ---------------------------------------------------------------------------

SEEN_TTL_DAYS = 36500 if HISTORICAL_MODE else 90


def load_seen() -> dict:
    if SEEN_FILE.exists():
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    return {}


def save_seen(seen: dict):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2)


def prune_seen(seen: dict) -> dict:
    """Remove entries older than SEEN_TTL_DAYS."""
    cutoff = (datetime.now() - timedelta(days=SEEN_TTL_DAYS)).isoformat()
    pruned = {k: v for k, v in seen.items() if v.get("first_seen", "") >= cutoff}
    removed = len(seen) - len(pruned)
    if removed:
        log.info(f"Pruned {removed} stale entries from seen hashes (>{SEEN_TTL_DAYS} days)")
    return pruned


# ---------------------------------------------------------------------------
# Parquet I/O
# ---------------------------------------------------------------------------


def append_rfps(rows: list[dict]) -> int:
    """Append new RFP rows to the Parquet file.  Returns count written."""
    if not rows:
        return 0

    new_table = pa.Table.from_pylist(rows, schema=RFP_SCHEMA)

    if PARQUET_FILE.exists():
        existing = pq.read_table(PARQUET_FILE)
        combined = pa.concat_tables([existing, new_table], promote_options="default")
    else:
        combined = new_table

    pq.write_table(combined, PARQUET_FILE, compression="snappy")

    size_mb = PARQUET_FILE.stat().st_size / (1024 * 1024)
    if size_mb > 500:
        log.warning(f"Parquet file is {size_mb:.1f} MB — consider partitioning")

    log.info(f"Wrote {len(rows)} new rows to {PARQUET_FILE.name} ({size_mb:.1f} MB total)")
    return len(rows)
