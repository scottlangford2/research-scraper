#!/usr/bin/env python3
"""
Research RFP Scraper — Phase 1: Federal Sources

Scrapes SAM.gov and Grants.gov, classifies by research keywords,
and stores all results in a Parquet dataset for analysis.

Author: Dr. W. Scott Langford / Lookout Analytics
"""

from datetime import datetime

from config import log
from filters import classify_rfp
from storage import rfp_hash, load_seen, save_seen, prune_seen, append_rfps
from sources import ALL_SOURCES


def main():
    log.info("=" * 60)
    log.info("Research scraper starting (Phase 1: Federal)")
    log.info("=" * 60)

    # --- Scrape all sources ---
    all_rfps: list[dict] = []
    for scrape_fn in ALL_SOURCES:
        try:
            results = scrape_fn()
            all_rfps.extend(results)
        except Exception as e:
            log.error(f"{scrape_fn.__name__} failed: {e}")

    log.info(f"Total raw RFPs scraped: {len(all_rfps)}")

    if not all_rfps:
        log.info("No RFPs scraped. Exiting.")
        return

    # --- Deduplicate ---
    seen = load_seen()
    new_rfps: list[dict] = []
    now = datetime.now()
    scrape_date = now.strftime("%Y-%m-%d")
    scrape_ts = now.isoformat()

    for rfp in all_rfps:
        h = rfp_hash(rfp)
        if h in seen:
            continue

        seen[h] = {
            "first_seen": now.isoformat(),
            "title": rfp.get("title", ""),
            "state": rfp.get("state", ""),
        }

        # --- Classify ---
        match, keywords = classify_rfp(rfp)

        new_rfps.append({
            "rfp_id": rfp.get("id", ""),
            "hash": h,
            "source": rfp.get("source", ""),
            "state": rfp.get("state", ""),
            "title": rfp.get("title", ""),
            "agency": rfp.get("agency", ""),
            "status": rfp.get("status", ""),
            "posted_date": rfp.get("posted_date", ""),
            "close_date": rfp.get("close_date", ""),
            "url": rfp.get("url", ""),
            "description": rfp.get("description", ""),
            "keyword_match": match,
            "matched_keywords": ", ".join(keywords),
            "scrape_date": scrape_date,
            "scrape_timestamp": now,
        })

    # --- Persist ---
    seen = prune_seen(seen)
    save_seen(seen)
    written = append_rfps(new_rfps)

    matched = sum(1 for r in new_rfps if r["keyword_match"])
    log.info(f"New RFPs: {written} ({matched} keyword matches, "
             f"{written - matched} unmatched)")
    log.info("Research scraper finished.")


if __name__ == "__main__":
    main()
