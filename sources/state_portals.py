"""
Individual state procurement portal scrapers.

Covers states with unique or less-common eProcurement platforms that don't
fit into the BuySpeed or JAGGAER shared scrapers.  Each portal is scraped
via Playwright using a common framework with per-state URL and selectors.
"""

import time

from config import PLAYWRIGHT_TIMEOUT, POLITE_DELAY, log

# ---------------------------------------------------------------------------
# State portal configurations
#
# Each entry defines:
#   state     — 2-letter abbreviation
#   label     — human-readable name
#   url       — public solicitation search page (no login required)
#   selectors — CSS selectors to find table rows, links, etc.
# ---------------------------------------------------------------------------

STATE_PORTALS = [
    # -- PeopleSoft / Oracle states --
    {
        "state": "CA",
        "label": "California Cal eProcure",
        "url": "https://caleprocure.ca.gov/pages/Events-BS3/event-search.aspx",
    },
    {
        "state": "CT",
        "label": "Connecticut CTsource",
        "url": "https://biznet.ct.gov/SCP_Search/BidResults.aspx",
    },
    {
        "state": "IN",
        "label": "Indiana IDOA",
        "url": "https://www.in.gov/idoa/procurement/current-business-opportunities/",
    },
    {
        "state": "KS",
        "label": "Kansas Procurement",
        "url": "https://admin.ks.gov/offices/procurement-and-contracts/bid-solicitations",
    },
    {
        "state": "MN",
        "label": "Minnesota Procurement",
        "url": "https://mn.gov/admin/government/procurement-contracting/open-solicitations/",
    },
    {
        "state": "ND",
        "label": "North Dakota OMB",
        "url": "https://www.omb.nd.gov/doing-business-state/current-bid-opportunities",
    },
    {
        "state": "TN",
        "label": "Tennessee Edison",
        "url": "https://tn.gov/generalservices/procurement/central-procurement-office--cpo-/opportunities.html",
    },
    {
        "state": "WI",
        "label": "Wisconsin VendorNet",
        "url": "https://vendornet.wi.gov/Bids.aspx",
    },
    # -- CGI / Advantage states --
    {
        "state": "KY",
        "label": "Kentucky eProcurement",
        "url": "https://finance.ky.gov/eProcurement/Pages/default.aspx",
    },
    {
        "state": "ME",
        "label": "Maine Purchases",
        "url": "https://www.maine.gov/dafs/bbm/procurementservices/vendors/current-bids",
    },
    {
        "state": "MI",
        "label": "Michigan SIGMA",
        "url": "https://www.michigan.gov/dtmb/procurement/contractconnect",
    },
    {
        "state": "WV",
        "label": "West Virginia Purchasing",
        "url": "https://www.state.wv.us/admin/purchase/Bids/default.html",
    },
    # -- SAP / Ariba states --
    {
        "state": "FL",
        "label": "Florida MFMP",
        "url": "https://vendor.myfloridamarketplace.com/search/bids/posted",
    },
    {
        "state": "LA",
        "label": "Louisiana LaPAC",
        "url": "https://wwwcfprd.doa.louisiana.gov/osp/lapac/pubMain.cfm",
    },
    {
        "state": "SC",
        "label": "South Carolina SCPRO",
        "url": "https://procurement.sc.gov/solicitations/current",
    },
    # -- Ivalua / other --
    {
        "state": "AL",
        "label": "Alabama Purchasing",
        "url": "https://procurement.alabama.gov/current-bid-opportunities/",
    },
    {
        "state": "AZ",
        "label": "Arizona APP",
        "url": "https://app.az.gov/page.aspx/en/rfx/rfx_browse/open",
    },
    {
        "state": "MD",
        "label": "Maryland eMMa",
        "url": "https://emma.maryland.gov/page.aspx/en/rfx/rfx_browse/open",
    },
    {
        "state": "OH",
        "label": "Ohio OhioBuys",
        "url": "https://ohiobuys.ohio.gov/page.aspx/en/rfx/rfx_browse/open",
    },
    {
        "state": "VT",
        "label": "Vermont Procurement",
        "url": "https://bgs.vermont.gov/purchasing/bids",
    },
    # -- Unique platform states --
    {
        "state": "AK",
        "label": "Alaska DOT Procurement",
        "url": "https://dot.alaska.gov/procurement/awp/bids.html",
    },
    {
        "state": "CO",
        "label": "Colorado OSC Solicitations",
        "url": "https://osc.colorado.gov/spco/solicitations",
    },
    {
        "state": "HI",
        "label": "Hawaii SPO",
        "url": "https://hands.ehawaii.gov/hands/opportunities",
    },
    {
        "state": "MS",
        "label": "Mississippi MAGIC",
        "url": "https://www.ms.gov/dfa/contract_bid_search",
    },
    {
        "state": "MO",
        "label": "Missouri MissouriBUYS",
        "url": "https://missouribuys.mo.gov/search/publicSolicitation",
    },
    {
        "state": "NE",
        "label": "Nebraska Materiel",
        "url": "https://das.nebraska.gov/materiel/bidopps.html",
    },
    {
        "state": "NH",
        "label": "New Hampshire Procurement",
        "url": "https://das.nh.gov/purchasing/bidscontracts/bids.aspx",
    },
    {
        "state": "NY",
        "label": "New York OGS Bids",
        "url": "https://ogs.ny.gov/procurement/bid-opportunities",
    },
    {
        "state": "RI",
        "label": "Rhode Island Purchasing",
        "url": "https://purchasing.ri.gov/RIVIP/ExternalBids.aspx",
    },
    {
        "state": "SD",
        "label": "South Dakota Procurement",
        "url": "https://www.sd.gov/bhra",
    },
    {
        "state": "VA",
        "label": "Virginia eVA",
        "url": "https://mvendor.cgieva.com/Vendor/public/AllOpportunities/",
    },
    {
        "state": "WA",
        "label": "Washington DES Contracts",
        "url": "https://apps.des.wa.gov/DESContracts/",
    },
    {
        "state": "WY",
        "label": "Wyoming Procurement",
        "url": "https://ai.wyo.gov/divisions/general-services/procurement/bid-opportunities",
    },
    # -- States already covered by dedicated scrapers (TX ESBD, NC eVP) --
    # TX: covered by texas_esbd.py
    # NC: covered by nc_evp.py
    # DE, ID: transitioned away from JAGGAER to new platforms
    {
        "state": "DE",
        "label": "Delaware MyMarketplace",
        "url": "https://mymarketplace.delaware.gov/bids",
    },
    {
        "state": "ID",
        "label": "Idaho Purchasing",
        "url": "https://purchasing.idaho.gov/bid-opportunities/",
    },
    {
        "state": "OK",
        "label": "Oklahoma OMES",
        "url": "https://oklahoma.gov/omes/services/purchasing/solicitations.html",
    },
]

STATE_PORTAL_MAX_PAGES = 5


def scrape_state_portals() -> list[dict]:
    """Scrape open solicitations from individual state portals."""
    log.info(
        f"Scraping {len(STATE_PORTALS)} individual state procurement portals..."
    )

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return _scrape_all_state_portals()
    except ImportError:
        log.warning(
            "Playwright not installed — skipping state portals. "
            "Install with: pip install playwright && python -m playwright install chromium"
        )
        return []


def _scrape_all_state_portals() -> list[dict]:
    from playwright.sync_api import sync_playwright

    all_rfps: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )

        for portal in STATE_PORTALS:
            try:
                rfps = _scrape_generic_portal(context, portal)
                all_rfps.extend(rfps)
            except Exception as e:
                log.error(f"  {portal['label']}: failed — {e}")

            time.sleep(POLITE_DELAY)

        browser.close()

    log.info(
        f"State portals total: {len(all_rfps)} solicitations "
        f"across {len(STATE_PORTALS)} portals"
    )
    return all_rfps


def _scrape_generic_portal(context, portal: dict) -> list[dict]:
    """Generic scraper for a single state portal.

    Uses a broad strategy: load the page, find tables and/or links
    that contain solicitation data, extract title + metadata.
    """
    state = portal["state"]
    label = portal["label"]
    url = portal["url"]
    rfps: list[dict] = []

    page = context.new_page()

    try:
        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT,
                  wait_until="domcontentloaded")

        # Give JS-rendered content time to load
        try:
            page.wait_for_selector(
                "table, .listing, .solicitation, .bid-list, .results, "
                ".opportunity, .content-area, main, article",
                timeout=20000,
            )
        except Exception:
            pass

        time.sleep(3)

        # --- Strategy 1: Table-based extraction ---
        rows = page.query_selector_all("table tbody tr")
        if rows:
            for row in rows:
                try:
                    rfp = _extract_from_table_row(row, state, label, url)
                    if rfp:
                        rfps.append(rfp)
                except Exception:
                    continue

        # --- Strategy 2: Link-based extraction (non-table pages) ---
        if not rfps:
            links = page.query_selector_all(
                "a[href*='solicitation'], a[href*='bid'], a[href*='opportunity'], "
                "a[href*='Solicitation'], a[href*='Bid'], a[href*='rfp'], "
                "a[href*='procurement'], a[href*='contract']"
            )

            seen_hrefs: set[str] = set()
            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    text = link.inner_text().strip()

                    # Filter out navigation/menu links
                    if not text or len(text) < 10:
                        continue
                    if href in seen_hrefs:
                        continue
                    seen_hrefs.add(href)

                    # Skip links that are clearly navigation
                    skip_words = {"home", "login", "register", "about", "contact",
                                  "faq", "help", "search", "back", "menu"}
                    if text.lower() in skip_words:
                        continue

                    rfps.append({
                        "state": state,
                        "source": label,
                        "id": _extract_id_from_url(href),
                        "title": text,
                        "agency": "",
                        "status": "Open",
                        "posted_date": "",
                        "close_date": "",
                        "url": _make_absolute(url, href),
                        "description": text,
                        "amount": "",
                    })
                except Exception:
                    continue

        # --- Strategy 3: Card/div-based extraction ---
        if not rfps:
            cards = page.query_selector_all(
                ".card, .list-item, .solicitation-item, .bid-item, "
                ".opportunity-card, .result-item, article"
            )
            for card in cards:
                try:
                    title_el = (
                        card.query_selector("h2, h3, h4, .title, a") or
                        card.query_selector("strong, b")
                    )
                    if not title_el:
                        continue
                    title = title_el.inner_text().strip()
                    if not title or len(title) < 10:
                        continue

                    link_el = card.query_selector("a[href]")
                    href = link_el.get_attribute("href") if link_el else ""

                    rfps.append({
                        "state": state,
                        "source": label,
                        "id": _extract_id_from_url(href) if href else "",
                        "title": title,
                        "agency": "",
                        "status": "Open",
                        "posted_date": "",
                        "close_date": "",
                        "url": _make_absolute(url, href) if href else "",
                        "description": title,
                        "amount": "",
                    })
                except Exception:
                    continue

        if rfps:
            log.info(f"  {label}: {len(rfps)} solicitations")
        else:
            log.info(f"  {label}: no solicitations found")

    except Exception as e:
        log.error(f"  {label}: scrape failed — {e}")
    finally:
        page.close()

    return rfps


def _extract_from_table_row(row, state: str, label: str, base_url: str) -> dict | None:
    """Extract an RFP from a table row."""
    import re

    cells = row.query_selector_all("td")
    if not cells or len(cells) < 2:
        return None

    link_el = row.query_selector("a[href]")
    href = link_el.get_attribute("href") if link_el else ""

    # Gather all cell text
    cell_texts = [c.inner_text().strip() for c in cells]

    # Title: prefer link text, then longest cell
    title = ""
    if link_el:
        title = link_el.inner_text().strip()
    if not title:
        title = max(cell_texts, key=len) if cell_texts else ""

    if not title or len(title) < 5:
        return None

    # ID: first short cell or from URL
    bid_id = ""
    for ct in cell_texts:
        if ct and len(ct) < 30 and ct != title:
            bid_id = ct
            break
    if not bid_id and href:
        bid_id = _extract_id_from_url(href)

    # Agency: second-longest non-title, non-date text
    agency = ""
    for ct in cell_texts:
        if ct and ct != title and ct != bid_id and len(ct) > 3:
            if not re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", ct):
                agency = ct
                break

    # Dates — collect all date-like cells; first is typically posted, last is close
    date_cells = []
    for ct in cell_texts:
        if re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", ct):
            date_cells.append(ct)

    posted_date = date_cells[0] if len(date_cells) > 1 else ""
    close_date = date_cells[-1] if date_cells else ""

    # Amount — look for dollar-like values
    amount = ""
    for ct in cell_texts:
        if re.search(r"\$[\d,.]+", ct):
            amount = ct
            break

    return {
        "state": state,
        "source": label,
        "id": bid_id,
        "title": title,
        "agency": agency,
        "status": "Open",
        "posted_date": posted_date,
        "close_date": close_date,
        "url": _make_absolute(base_url, href) if href else "",
        "description": title,
        "amount": amount,
    }


def _extract_id_from_url(href: str) -> str:
    """Try to extract a bid/solicitation ID from a URL."""
    import re
    # Common patterns
    for pattern in [
        r"[Ii]d=(\w+)", r"bid[Ii]d=(\w+)", r"solicitation[Ii]d=(\w+)",
        r"doc[Ii]d=(\w+)", r"number=(\w+)",
    ]:
        match = re.search(pattern, href)
        if match:
            return match.group(1)
    # Fallback: last path segment
    parts = href.rstrip("/").split("/")
    if parts:
        last = parts[-1].split("?")[0]
        if last and last != "default.aspx" and last != "index.html":
            return last
    return ""


def _make_absolute(base_url: str, href: str) -> str:
    """Ensure href is absolute."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    from urllib.parse import urljoin
    return urljoin(base_url, href)
