"""
DemandStar scraper — local government solicitations.

Scrapes open bids from demandstar.com/app/browse-bids by state using Playwright.
DemandStar aggregates bids from 1,400+ local government agencies nationwide.
"""

import time

from config import DEMANDSTAR_MAX_PAGES, PLAYWRIGHT_TIMEOUT, POLITE_DELAY, log

# ---------------------------------------------------------------------------
# State slug → abbreviation mapping
# ---------------------------------------------------------------------------

STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new-hampshire": "NH", "new-jersey": "NJ",
    "new-mexico": "NM", "new-york": "NY", "north-carolina": "NC",
    "north-dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode-island": "RI", "south-carolina": "SC",
    "south-dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west-virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


def scrape_demandstar() -> list[dict]:
    """Scrape DemandStar open bids for all 50 states."""
    log.info("Scraping DemandStar (all 50 states)...")

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return _scrape_all_states()
    except ImportError:
        log.warning(
            "Playwright not installed — skipping DemandStar. "
            "Install with: pip install playwright && python -m playwright install chromium"
        )
        return []


def _scrape_all_states() -> list[dict]:
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
                state_rfps = _scrape_state(context, slug, abbrev)
                all_rfps.extend(state_rfps)
            except Exception as e:
                log.error(f"  DemandStar {abbrev}: failed — {e}")

            time.sleep(POLITE_DELAY)

        browser.close()

    log.info(f"DemandStar total: {len(all_rfps)} solicitations across 50 states")
    return all_rfps


def _scrape_state(context, slug: str, abbrev: str) -> list[dict]:
    """Scrape one state's open bids from DemandStar."""
    rfps: list[dict] = []
    page = context.new_page()

    try:
        url = f"https://www.demandstar.com/app/browse-bids/states/{slug}"
        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")

        # DemandStar is a React SPA — wait for bid content to render
        try:
            page.wait_for_selector(
                "[class*='bid'], [class*='Bid'], table, [class*='card'], "
                "[class*='solicitation'], [class*='listing'], [class*='result']",
                timeout=15000,
            )
        except Exception:
            log.info(f"  DemandStar {abbrev}: no bid content loaded")
            return rfps

        time.sleep(2)

        page_num = 1
        while page_num <= DEMANDSTAR_MAX_PAGES:
            # Try multiple selectors for bid rows/cards
            rows = (
                page.query_selector_all("[class*='bid-row'], [class*='bid-card']") or
                page.query_selector_all("[class*='BidRow'], [class*='BidCard']") or
                page.query_selector_all("table tbody tr") or
                page.query_selector_all("[class*='result-item'], [class*='listing-item']")
            )

            if not rows:
                # Fallback: link-based extraction
                links = page.query_selector_all(
                    "a[href*='/bid/'], a[href*='/bids/'], a[href*='/solicitation']"
                )
                for link in links:
                    href = link.get_attribute("href") or ""
                    text = link.inner_text().strip()
                    if text and len(text) > 10:
                        parts = href.rstrip("/").split("/")
                        sol_id = parts[-1] if parts else ""
                        rfps.append({
                            "state": abbrev,
                            "source": "DemandStar",
                            "id": sol_id,
                            "title": text,
                            "agency": "",
                            "status": "Open",
                            "posted_date": "",
                            "close_date": "",
                            "url": href if href.startswith("http")
                                   else f"https://www.demandstar.com{href}",
                            "description": text,
                        })
                break

            for row in rows:
                try:
                    title_el = (
                        row.query_selector(
                            "h3, h4, [class*='title'], [class*='Title'], "
                            "[class*='name'], [class*='Name']"
                        ) or row.query_selector("a")
                    )
                    title = title_el.inner_text().strip() if title_el else ""

                    link_el = row.query_selector("a[href]")
                    href = link_el.get_attribute("href") if link_el else ""

                    agency_el = row.query_selector(
                        "[class*='agency'], [class*='Agency'], "
                        "[class*='organization'], [class*='Organization'], "
                        "[class*='entity'], [class*='Entity']"
                    )
                    agency = agency_el.inner_text().strip() if agency_el else ""

                    date_el = row.query_selector(
                        "[class*='close'], [class*='Close'], "
                        "[class*='deadline'], [class*='Deadline'], "
                        "[class*='due'], [class*='Due'], [class*='end'], [class*='End']"
                    )
                    close_date = date_el.inner_text().strip() if date_el else ""

                    posted_el = row.query_selector(
                        "[class*='post'], [class*='Post'], "
                        "[class*='publish'], [class*='Publish'], "
                        "[class*='start'], [class*='Start']"
                    )
                    posted_date = posted_el.inner_text().strip() if posted_el else ""

                    parts = (href or "").rstrip("/").split("/")
                    sol_id = parts[-1] if parts else ""

                    if title:
                        rfps.append({
                            "state": abbrev,
                            "source": "DemandStar",
                            "id": sol_id,
                            "title": title,
                            "agency": agency,
                            "status": "Open",
                            "posted_date": posted_date,
                            "close_date": close_date,
                            "url": (href if href and href.startswith("http")
                                    else f"https://www.demandstar.com{href}"
                                    if href else ""),
                            "description": title,
                        })
                except Exception:
                    continue

            # Try next page
            next_btn = (
                page.query_selector(
                    "a.next, .pagination .next a, a[aria-label='Next'], "
                    "button[aria-label='Next'], [class*='next'] a, "
                    "li.next a, a:has-text('Next'), button:has-text('Next'), "
                    "a:has-text('>'), button:has-text('>')"
                )
            )

            if next_btn:
                try:
                    next_btn.click(timeout=10000, no_wait_after=True)
                    time.sleep(3)
                    page_num += 1
                except Exception:
                    break
            else:
                break

        if rfps:
            log.info(f"  DemandStar {abbrev}: {len(rfps)} solicitations")

    except Exception as e:
        log.error(f"  DemandStar {abbrev}: scrape failed — {e}")
    finally:
        page.close()

    return rfps
