"""
BidNet Direct scraper — all 50 US states.

Scrapes local government solicitations from bidnetdirect.com using Playwright.
Each state has its own URL slug; we iterate all 50 in a single browser session.
"""

import time

from config import BIDNET_MAX_PAGES_PER_STATE, PLAYWRIGHT_TIMEOUT, POLITE_DELAY, log

# ---------------------------------------------------------------------------
# State slug → abbreviation mapping
# ---------------------------------------------------------------------------

STATES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new-hampshire": "NH",
    "new-jersey": "NJ",
    "new-mexico": "NM",
    "new-york": "NY",
    "north-carolina": "NC",
    "north-dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode-island": "RI",
    "south-carolina": "SC",
    "south-dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west-virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}


def scrape_bidnet() -> list[dict]:
    """Scrape BidNet Direct open solicitations for all 50 states."""
    log.info("Scraping BidNet Direct (all 50 states)...")

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return _scrape_bidnet_all_states()
    except ImportError:
        log.warning(
            "Playwright not installed — skipping BidNet Direct. "
            "Install with: pip install playwright && python -m playwright install chromium"
        )
        return []


def _scrape_bidnet_all_states() -> list[dict]:
    from playwright.sync_api import sync_playwright

    all_rfps: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )

        for slug, abbrev in STATES.items():
            try:
                state_rfps = _scrape_bidnet_state(context, slug, abbrev)
                all_rfps.extend(state_rfps)
            except Exception as e:
                log.error(f"  BidNet {abbrev}: failed — {e}")

            time.sleep(POLITE_DELAY)

        browser.close()

    log.info(f"BidNet Direct total: {len(all_rfps)} solicitations across 50 states")
    return all_rfps


def _scrape_bidnet_state(context, slug: str, abbrev: str) -> list[dict]:
    """Scrape one state's open bids from BidNet Direct."""
    rfps: list[dict] = []
    page = context.new_page()

    try:
        url = f"https://www.bidnetdirect.com/{slug}/solicitations/open-bids"
        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT,
                  wait_until="domcontentloaded")

        # Wait for content to load
        try:
            page.wait_for_selector(
                ".bids-list, .solicitation-list, table, .results, .no-results",
                timeout=15000,
            )
        except Exception:
            log.info(f"  BidNet {abbrev}: page did not load expected selectors")
            return rfps

        time.sleep(2)

        page_num = 1
        while page_num <= BIDNET_MAX_PAGES_PER_STATE:
            # Try multiple possible listing selectors
            rows = (
                page.query_selector_all(".bid-card, .solicitation-card") or
                page.query_selector_all("table tbody tr") or
                page.query_selector_all(".search-result, .result-item")
            )

            if not rows:
                # Fallback: link-based extraction
                links = page.query_selector_all("a[href*='/solicitations/']")
                for link in links:
                    href = link.get_attribute("href") or ""
                    text = link.inner_text().strip()
                    if text and len(text) > 10 and "/open-bids" not in href:
                        parts = href.rstrip("/").split("/")
                        sol_id = parts[-1] if parts else ""
                        rfps.append({
                            "state": abbrev,
                            "source": "BidNet Direct",
                            "id": sol_id,
                            "title": text,
                            "agency": "",
                            "status": "Open",
                            "posted_date": "",
                            "close_date": "",
                            "url": href if href.startswith("http")
                                   else f"https://www.bidnetdirect.com{href}",
                            "description": text,
                        })
                break

            for row in rows:
                try:
                    title_el = (
                        row.query_selector("h3, h4, .title, .bid-title") or
                        row.query_selector("a")
                    )
                    title = title_el.inner_text().strip() if title_el else ""

                    link_el = row.query_selector("a[href]")
                    href = link_el.get_attribute("href") if link_el else ""

                    agency_el = row.query_selector(
                        ".agency, .organization, .department, .entity-name"
                    )
                    agency = agency_el.inner_text().strip() if agency_el else ""

                    date_el = row.query_selector(
                        ".close-date, .deadline, .due-date, .end-date"
                    )
                    close_date = date_el.inner_text().strip() if date_el else ""

                    posted_el = row.query_selector(
                        ".post-date, .posted-date, .publish-date"
                    )
                    posted_date = posted_el.inner_text().strip() if posted_el else ""

                    parts = (href or "").rstrip("/").split("/")
                    sol_id = parts[-1] if parts else ""

                    if title:
                        rfps.append({
                            "state": abbrev,
                            "source": "BidNet Direct",
                            "id": sol_id,
                            "title": title,
                            "agency": agency,
                            "status": "Open",
                            "posted_date": posted_date,
                            "close_date": close_date,
                            "url": (href if href and href.startswith("http")
                                    else f"https://www.bidnetdirect.com{href}" if href else ""),
                            "description": title,
                        })
                except Exception:
                    continue

            # Try next page
            next_btn = (
                page.query_selector("a.next, .pagination .next a, a[aria-label='Next']") or
                page.query_selector("li.next a, a:has-text('Next'), a:has-text('>')")
            )

            if next_btn:
                try:
                    # Use no_wait_after to prevent hanging on navigation
                    next_btn.click(timeout=10000, no_wait_after=True)
                    time.sleep(4)

                    for _ in range(10):
                        new_rows = (
                            page.query_selector_all(".bid-card, .solicitation-card") or
                            page.query_selector_all("table tbody tr")
                        )
                        if new_rows:
                            break
                        time.sleep(1)

                    page_num += 1
                except Exception:
                    break
            else:
                break

        if rfps:
            log.info(f"  BidNet {abbrev}: {len(rfps)} solicitations")

    except Exception as e:
        log.error(f"  BidNet {abbrev}: scrape failed — {e}")
    finally:
        page.close()

    return rfps
