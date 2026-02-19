"""
JAGGAER / SciQuest scraper — states using the JAGGAER eProcurement platform.

JAGGAER (formerly SciQuest) powers eProcurement for several US states.
Public bid events are accessible via the /PublicEvent endpoint.
"""

import time

from config import PLAYWRIGHT_TIMEOUT, POLITE_DELAY, log

# ---------------------------------------------------------------------------
# JAGGAER portal configurations
# ---------------------------------------------------------------------------

JAGGAER_PORTALS = [
    {
        "state": "GA",
        "label": "Georgia TGM",
        "url": "https://ssl.doas.state.ga.us/PRSapp/PR_index.jsp",
        "type": "custom",  # Georgia uses a custom page, not standard JAGGAER
    },
    {
        "state": "IA",
        "label": "Iowa IMPACS",
        "url": "https://bids.sciquest.com/apps/Router/PublicEvent?CustomerOrg=DASIowa",
        "type": "jaggaer",
    },
    {
        "state": "MT",
        "label": "Montana eProcurement",
        "url": "https://solutions.sciquest.com/apps/Router/PublicEvent?CustomerOrg=StateOfMontana",
        "type": "jaggaer",
    },
    {
        "state": "NM",
        "label": "New Mexico eProNM",
        "url": "https://solutions.sciquest.com/apps/Router/PublicEvent?CustomerOrg=StateOfNewMexico",
        "type": "jaggaer",
    },
    {
        "state": "PA",
        "label": "Pennsylvania eMarketplace",
        "url": "https://www.emarketplace.state.pa.us/Solicitations.aspx",
        "type": "custom",  # PA uses a custom .NET interface
    },
    {
        "state": "UT",
        "label": "Utah Procurement",
        "url": "https://solutions.sciquest.com/apps/Router/PublicEvent?CustomerOrg=StateOfUtah",
        "type": "jaggaer",
    },
]

JAGGAER_MAX_PAGES = 10


def scrape_jaggaer() -> list[dict]:
    """Scrape open solicitations from all JAGGAER portals."""
    log.info(f"Scraping {len(JAGGAER_PORTALS)} JAGGAER/SciQuest state portals...")

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return _scrape_all_portals()
    except ImportError:
        log.warning(
            "Playwright not installed — skipping JAGGAER portals. "
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

        for portal in JAGGAER_PORTALS:
            try:
                rfps = _scrape_one_portal(context, portal)
                all_rfps.extend(rfps)
            except Exception as e:
                log.error(f"  {portal['label']}: failed — {e}")

            time.sleep(POLITE_DELAY)

        browser.close()

    log.info(
        f"JAGGAER total: {len(all_rfps)} solicitations "
        f"across {len(JAGGAER_PORTALS)} portals"
    )
    return all_rfps


def _scrape_one_portal(context, portal: dict) -> list[dict]:
    """Scrape open events from one JAGGAER portal."""
    state = portal["state"]
    label = portal["label"]
    url = portal["url"]
    rfps: list[dict] = []

    page = context.new_page()

    try:
        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT,
                  wait_until="domcontentloaded")

        # Wait for content
        try:
            page.wait_for_selector(
                "table, .event-list, .search-results, .public-event-list, "
                "#bidSearchResultsTable, .results",
                timeout=20000,
            )
        except Exception:
            log.info(f"  {label}: page did not load expected selectors")
            return rfps

        time.sleep(3)

        page_num = 1
        while page_num <= JAGGAER_MAX_PAGES:
            # JAGGAER public event pages show event tables
            rows = (
                page.query_selector_all("table tbody tr") or
                page.query_selector_all(".event-list-item, .event-row") or
                page.query_selector_all("tr.odd, tr.even")
            )

            if not rows:
                # Fallback: extract any links that look like events
                links = page.query_selector_all(
                    "a[href*='Event'], a[href*='event'], a[href*='PublicEvent']"
                )
                for link in links:
                    href = link.get_attribute("href") or ""
                    text = link.inner_text().strip()
                    if text and len(text) > 10:
                        rfps.append({
                            "state": state,
                            "source": label,
                            "id": _extract_event_id(href),
                            "title": text,
                            "agency": "",
                            "status": "Open",
                            "posted_date": "",
                            "close_date": "",
                            "url": href if href.startswith("http")
                                   else f"{url.split('/apps')[0]}{href}",
                            "description": text,
                            "amount": "",
                        })
                break

            for row in rows:
                try:
                    cells = row.query_selector_all("td")
                    if not cells or len(cells) < 2:
                        continue

                    link_el = row.query_selector("a[href]")
                    href = link_el.get_attribute("href") if link_el else ""

                    # Event ID
                    event_id = cells[0].inner_text().strip() if cells else ""
                    if not event_id and href:
                        event_id = _extract_event_id(href)

                    # Title
                    title = ""
                    if link_el:
                        title = link_el.inner_text().strip()
                    if not title and len(cells) > 1:
                        title = cells[1].inner_text().strip()

                    # Agency
                    agency = ""
                    for i in range(2, min(len(cells), 5)):
                        ct = cells[i].inner_text().strip()
                        if ct and not _looks_like_date(ct) and len(ct) > 3:
                            agency = ct
                            break

                    # Dates — collect all date-like cells
                    date_cells = []
                    for i in range(2, len(cells)):
                        ct = cells[i].inner_text().strip()
                        if _looks_like_date(ct):
                            date_cells.append(ct)

                    posted_date = date_cells[0] if len(date_cells) > 1 else ""
                    close_date = date_cells[-1] if date_cells else ""

                    # Amount — look for dollar-like values
                    amount = ""
                    for i in range(2, len(cells)):
                        ct = cells[i].inner_text().strip()
                        if _looks_like_amount(ct):
                            amount = ct
                            break

                    if title:
                        rfps.append({
                            "state": state,
                            "source": label,
                            "id": event_id,
                            "title": title,
                            "agency": agency,
                            "status": "Open",
                            "posted_date": posted_date,
                            "close_date": close_date,
                            "url": href if href and href.startswith("http")
                                   else "",
                            "description": title,
                            "amount": amount,
                        })
                except Exception:
                    continue

            # Pagination
            next_btn = (
                page.query_selector("a.next, .next a, a[aria-label='Next']") or
                page.query_selector("a:has-text('Next'), a:has-text('>')")
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

import re  # noqa: E402

def _extract_event_id(href: str) -> str:
    """Try to pull event ID from a JAGGAER URL."""
    match = re.search(r"[Ee]vent[Ii]d=(\d+)", href)
    if match:
        return match.group(1)
    match = re.search(r"docId=(\d+)", href)
    if match:
        return match.group(1)
    return ""


def _looks_like_date(text: str) -> bool:
    return bool(re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text))


def _looks_like_amount(text: str) -> bool:
    return bool(re.search(r"\$[\d,.]+", text) or
                re.search(r"^[\d,.]+$", text.strip()) and len(text.strip()) > 3)
