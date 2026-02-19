"""
BuySpeed / Periscope ePro (BSO) scraper — shared platform states.

Many state and local governments use the Periscope Holdings BuySpeed platform
(identifiable by the /bso/ URL path). All share the same HTML structure, so
one scraper handles all of them.

Public open-bids URL pattern (current):
    https://{domain}/bso/view/search/external/advancedSearchBid.xhtml?openBids=true
"""

import time

from config import PLAYWRIGHT_TIMEOUT, POLITE_DELAY, log

# ---------------------------------------------------------------------------
# BuySpeed portal configurations
# ---------------------------------------------------------------------------

BUYSPEED_PORTALS = [
    {
        "state": "AR",
        "label": "Arkansas ARBuy",
        "url": "https://arbuy.arkansas.gov/bso/view/search/external/advancedSearchBid.xhtml?openBids=true",
    },
    {
        "state": "IL",
        "label": "Illinois BidBuy",
        "url": "https://www.bidbuy.illinois.gov/bso/view/search/external/advancedSearchBid.xhtml?openBids=true",
    },
    {
        "state": "MA",
        "label": "Massachusetts COMMBUYS",
        "url": "https://www.commbuys.com/bso/view/search/external/advancedSearchBid.xhtml?openBids=true",
    },
    {
        "state": "NV",
        "label": "Nevada NEVADAePro",
        "url": "https://nevadaepro.com/bso/view/search/external/advancedSearchBid.xhtml?openBids=true",
    },
    {
        "state": "NJ",
        "label": "New Jersey NJSTART",
        "url": "https://www.njstart.gov/bso/view/search/external/advancedSearchBid.xhtml?openBids=true",
    },
    {
        "state": "OR",
        "label": "Oregon OregonBuys",
        "url": "https://oregonbuys.gov/bso/view/search/external/advancedSearchBid.xhtml?openBids=true",
    },
]

BUYSPEED_MAX_PAGES = 10


def scrape_buyspeed() -> list[dict]:
    """Scrape open solicitations from all BuySpeed/BSO portals."""
    log.info(f"Scraping {len(BUYSPEED_PORTALS)} BuySpeed/BSO state portals...")

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return _scrape_all_portals()
    except ImportError:
        log.warning(
            "Playwright not installed — skipping BuySpeed portals. "
            "Install with: pip install playwright && python -m playwright install chromium"
        )
        return []


def _scrape_all_portals() -> list[dict]:
    from playwright.sync_api import sync_playwright

    all_rfps: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )

        for portal in BUYSPEED_PORTALS:
            try:
                rfps = _scrape_one_portal(context, portal)
                all_rfps.extend(rfps)
            except Exception as e:
                log.error(f"  {portal['label']}: failed — {e}")

            time.sleep(POLITE_DELAY)

        browser.close()

    log.info(
        f"BuySpeed total: {len(all_rfps)} solicitations "
        f"across {len(BUYSPEED_PORTALS)} portals"
    )
    return all_rfps


def _scrape_one_portal(context, portal: dict) -> list[dict]:
    """Scrape open bids from a single BuySpeed/BSO portal."""
    state = portal["state"]
    label = portal["label"]
    url = portal["url"]
    rfps: list[dict] = []

    page = context.new_page()

    try:
        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT,
                  wait_until="domcontentloaded")

        # The advancedSearchBid page loads a form; we need to click
        # the "Search" button to get results, or it may auto-populate.
        time.sleep(3)

        # Try clicking a search/submit button if present
        search_btn = (
            page.query_selector("input[type='submit'][value='Search']") or
            page.query_selector("button:has-text('Search')") or
            page.query_selector("input.button[value='Search']") or
            page.query_selector("a:has-text('Search')")
        )
        if search_btn:
            try:
                search_btn.click()
                time.sleep(3)
            except Exception:
                pass

        # Wait for the bid table or "no results" message
        try:
            page.wait_for_selector(
                "table, .dataTables_wrapper, .bid-table, "
                ".no-results, #bidSearchResultsTable, .results-table, "
                ".search-results, .bid-results",
                timeout=15000,
            )
        except Exception:
            log.info(f"  {label}: page did not load expected selectors")
            return rfps

        time.sleep(2)

        page_num = 1
        while page_num <= BUYSPEED_MAX_PAGES:
            # BuySpeed tables typically have a results table
            rows = (
                page.query_selector_all("table.table tbody tr") or
                page.query_selector_all("#bidSearchResultsTable tbody tr") or
                page.query_selector_all("table tbody tr")
            )

            if not rows:
                # Try link-based fallback
                links = page.query_selector_all(
                    "a[href*='bidDetail'], a[href*='BidDetail'], "
                    "a[href*='publicBidDetail']"
                )
                for link in links:
                    href = link.get_attribute("href") or ""
                    text = link.inner_text().strip()
                    if text and len(text) > 5:
                        rfps.append({
                            "state": state,
                            "source": label,
                            "id": _extract_bid_id(href),
                            "title": text,
                            "agency": "",
                            "status": "Open",
                            "posted_date": "",
                            "close_date": "",
                            "url": _make_absolute(url, href),
                            "description": text,
                            "amount": "",
                        })
                break

            for row in rows:
                try:
                    cells = row.query_selector_all("td")
                    if not cells or len(cells) < 2:
                        continue

                    # BuySpeed tables vary, but common patterns:
                    # Col 0: Bid number/ID  Col 1: Description/Title
                    # Col 2: Agency/Org  Col 3: Close date
                    link_el = row.query_selector("a[href]")
                    href = link_el.get_attribute("href") if link_el else ""

                    # Try to extract bid ID from first cell or link
                    bid_id = ""
                    if cells:
                        bid_id = cells[0].inner_text().strip()
                    if not bid_id and href:
                        bid_id = _extract_bid_id(href)

                    # Title from link text or second cell
                    title = ""
                    if link_el:
                        title = link_el.inner_text().strip()
                    if not title and len(cells) > 1:
                        title = cells[1].inner_text().strip()
                    if not title:
                        title = bid_id

                    # Agency — typically 3rd or 4th column
                    agency = ""
                    for i in range(2, min(len(cells), 5)):
                        cell_text = cells[i].inner_text().strip()
                        if cell_text and not _looks_like_date(cell_text):
                            agency = cell_text
                            break

                    # Dates — collect all date-like cells; first is typically
                    # posted/open date, second is close date
                    date_cells = []
                    for i in range(2, len(cells)):
                        cell_text = cells[i].inner_text().strip()
                        if _looks_like_date(cell_text):
                            date_cells.append(cell_text)

                    posted_date = date_cells[0] if len(date_cells) > 1 else ""
                    close_date = date_cells[-1] if date_cells else ""

                    # Amount — look for dollar-like values
                    amount = ""
                    for i in range(2, len(cells)):
                        cell_text = cells[i].inner_text().strip()
                        if _looks_like_amount(cell_text):
                            amount = cell_text
                            break

                    # Skip navigation cruft and header rows
                    skip_words = {"select category", "bid solicitations",
                                  "contracts", "purchase orders", "search",
                                  "filter", "sort by", "category"}
                    if title and not any(sw in title.lower() for sw in skip_words):
                        rfps.append({
                            "state": state,
                            "source": label,
                            "id": bid_id,
                            "title": title,
                            "agency": agency,
                            "status": "Open",
                            "posted_date": posted_date,
                            "close_date": close_date,
                            "url": _make_absolute(url, href) if href else "",
                            "description": title,
                            "amount": amount,
                        })
                except Exception:
                    continue

            # Try next page
            next_btn = (
                page.query_selector("a.next, .pagination .next a") or
                page.query_selector("a[aria-label='Next'], a:has-text('Next')") or
                page.query_selector("li.next a, a:has-text('>')")
            )

            if next_btn and next_btn.is_visible():
                try:
                    next_btn.click()
                    time.sleep(3)
                    page_num += 1
                except Exception:
                    break
            else:
                break

        if rfps:
            log.info(f"  {label}: {len(rfps)} solicitations")

    except Exception as e:
        log.error(f"  {label}: scrape failed — {e}")
    finally:
        page.close()

    return rfps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_bid_id(href: str) -> str:
    """Try to pull a bid ID from a BuySpeed URL."""
    # Typical: /bso/external/publicBidDetail.sdo?bidId=12345
    import re
    match = re.search(r"bidId=(\d+)", href)
    if match:
        return match.group(1)
    parts = href.rstrip("/").split("/")
    return parts[-1] if parts else ""


def _looks_like_date(text: str) -> bool:
    """Quick heuristic: does this string look like a date?"""
    import re
    return bool(re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text))


def _looks_like_amount(text: str) -> bool:
    """Quick heuristic: does this string look like a dollar amount?"""
    import re
    return bool(re.search(r"\$[\d,.]+", text) or
                re.search(r"^[\d,.]+$", text.strip()) and len(text.strip()) > 3)


def _make_absolute(base_url: str, href: str) -> str:
    """Ensure href is absolute, using base_url's domain."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    from urllib.parse import urljoin
    return urljoin(base_url, href)
