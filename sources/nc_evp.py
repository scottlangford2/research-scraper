"""
North Carolina eVP (eProcurement @ Your Service) scraper.

The site is built on Microsoft Power Pages and renders the solicitation
grid via client-side JavaScript. Requires Playwright for full data.
Falls back to a requests-based scraper with limited results.
"""

import time

import requests
from bs4 import BeautifulSoup

from config import NC_EVP_MAX_PAGES, REQUEST_TIMEOUT, PLAYWRIGHT_TIMEOUT, POLITE_DELAY, log


def scrape_nc_evp() -> list[dict]:
    log.info("Scraping North Carolina eVP...")
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return _scrape_nc_evp_playwright()
    except ImportError:
        log.warning(
            "Playwright not installed — falling back to requests-based NC scraper. "
            "Install with: pip install playwright && python -m playwright install chromium"
        )
        return _scrape_nc_evp_requests()


def _scrape_nc_evp_playwright() -> list[dict]:
    from playwright.sync_api import sync_playwright

    rfps: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto("https://evp.nc.gov/solicitations/", timeout=PLAYWRIGHT_TIMEOUT)
            page.wait_for_selector(
                "table.table tbody tr, .view-empty.message:not(.hidden)",
                timeout=30000,
            )
            time.sleep(3)

            page_num = 1
            while page_num <= NC_EVP_MAX_PAGES:
                rows = page.query_selector_all("table.table tbody tr")
                if not rows:
                    log.info(f"  NC eVP page {page_num}: no rows found")
                    break

                for row in rows:
                    cells = row.query_selector_all("td")
                    if not cells:
                        continue

                    cell_texts = [c.inner_text().strip() for c in cells]
                    link_el = row.query_selector("a")
                    href = link_el.get_attribute("href") if link_el else ""

                    # Columns: 0=Sol Number, 1=Title, 2=Description,
                    #          3=Opening Date, 4=Posted Date, 5=Status, 6=Department
                    rfps.append({
                        "state": "NC",
                        "source": "NC eVP",
                        "id": cell_texts[0] if len(cell_texts) > 0 else "",
                        "title": cell_texts[1] if len(cell_texts) > 1 else "",
                        "agency": cell_texts[6] if len(cell_texts) > 6 else "",
                        "status": cell_texts[5] if len(cell_texts) > 5 else "",
                        "posted_date": cell_texts[4] if len(cell_texts) > 4 else "",
                        "close_date": cell_texts[3] if len(cell_texts) > 3 else "",
                        "url": (f"https://evp.nc.gov{href}" if href and href.startswith("/")
                                else (href or "")),
                        "description": cell_texts[2] if len(cell_texts) > 2 else "",
                    })

                log.info(f"  NC eVP page {page_num}: {len(rows)} rows")

                # Paginate via ">" link
                pag_items = page.query_selector_all(".pagination li")
                next_btn = None
                for li in pag_items:
                    text = li.inner_text().strip()
                    disabled = li.get_attribute("class") or ""
                    if text == ">" and "disabled" not in disabled:
                        next_btn = li.query_selector("a")
                        break

                if next_btn:
                    old_first = ""
                    first_row = page.query_selector("table.table tbody tr td")
                    if first_row:
                        old_first = first_row.inner_text().strip()

                    next_btn.click()
                    time.sleep(2)

                    for _ in range(10):
                        new_first = ""
                        first_row = page.query_selector("table.table tbody tr td")
                        if first_row:
                            new_first = first_row.inner_text().strip()
                        if new_first and new_first != old_first:
                            break
                        time.sleep(1)
                    else:
                        log.info("  NC eVP: grid did not refresh, stopping")
                        break

                    time.sleep(1)
                    page_num += 1
                else:
                    break

        except Exception as e:
            log.error(f"NC eVP Playwright scrape failed: {e}")
        finally:
            browser.close()

    log.info(f"NC eVP total: {len(rfps)} solicitations")
    return rfps


def _scrape_nc_evp_requests() -> list[dict]:
    """Fallback: scrape NC DOA procurement page for any posted links."""
    rfps: list[dict] = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    })

    try:
        resp = session.get(
            "https://www.doa.nc.gov/divisions/purchase-contract",
            timeout=REQUEST_TIMEOUT,
        )
        if resp.ok:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if ("solicitation" in href.lower() or "solicitation" in text.lower()
                        or "rfp" in text.lower() or "bid" in text.lower()):
                    if len(text) > 10:
                        rfps.append({
                            "state": "NC",
                            "source": "NC DOA",
                            "id": "",
                            "title": text,
                            "agency": "NC Dept. of Administration",
                            "status": "",
                            "posted_date": "",
                            "close_date": "",
                            "url": href if href.startswith("http") else f"https://www.doa.nc.gov{href}",
                            "description": "",
                        })
    except requests.RequestException as e:
        log.warning(f"NC DOA fallback failed: {e}")

    log.info(f"NC requests fallback: {len(rfps)} items")
    return rfps
