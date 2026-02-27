#!/usr/bin/env python3
"""
Research RFP Scraper

Scrapes federal sources (SAM.gov, Grants.gov), aggregators (BidNet, Socrata),
and all 50 state procurement portals. Classifies by research keywords,
extracts key terms, and stores results in a Parquet dataset.

Author: Dr. W. Scott Langford / Lookout Analytics
"""

import subprocess
from datetime import datetime
from pathlib import Path

from config import log
from filters import classify_rfp
from keywords import extract_key_terms
from storage import rfp_hash, load_seen, save_seen, prune_seen, append_rfps
from analyze_keywords import run_analysis
from generate_site import generate_site
from sources import ALL_SOURCES


def main():
    log.info("=" * 60)
    log.info("Research scraper starting")
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

        # --- Classify (deductive) ---
        match, keywords = classify_rfp(rfp)

        # --- Extract key terms (inductive) ---
        key_terms = extract_key_terms(rfp)

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
            "amount": rfp.get("amount", ""),
            "keyword_match": match,
            "matched_keywords": ", ".join(keywords),
            "key_terms": ", ".join(key_terms),
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

    # --- Corpus-level keyword analysis ---
    log.info("Running corpus-level keyword analysis...")
    try:
        summary = run_analysis()
        log.info(summary)
    except Exception as e:
        log.error(f"Keyword analysis failed: {e}")

    # --- Generate summary dashboard ---
    log.info("Generating summary dashboard...")
    try:
        site_summary = generate_site()
        log.info(site_summary)
    except Exception as e:
        log.error(f"Site generation failed: {e}")

    # --- Push updated dashboard to GitHub Pages ---
    log.info("Pushing dashboard to GitHub Pages...")
    try:
        repo_dir = Path(__file__).resolve().parent
        subprocess.run(
            ["git", "add", "docs/index.html"],
            cwd=repo_dir, check=True, capture_output=True,
        )
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_dir, capture_output=True,
        )
        if result.returncode != 0:  # there are staged changes
            subprocess.run(
                ["git", "commit", "-m",
                 f"Daily dashboard update: {written} new RFPs ({scrape_date})"],
                cwd=repo_dir, check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "push"],
                cwd=repo_dir, check=True, capture_output=True,
            )
            log.info("Dashboard pushed to GitHub Pages.")
        else:
            log.info("No dashboard changes to push.")
    except Exception as e:
        log.error(f"Git push failed: {e}")

    log.info("Research scraper finished.")


if __name__ == "__main__":
    main()
