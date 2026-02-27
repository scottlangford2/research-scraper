"""
New York State Contract Reporter (NYSCR) scraper.

Scrapes the NYSCR IframeSearch endpoint for open solicitations.
Server-rendered HTML, no authentication required.
"""

import time

import requests
from bs4 import BeautifulSoup

from config import NY_NYSCR_MAX_PAGES, REQUEST_TIMEOUT, POLITE_DELAY, log


def scrape_ny_nyscr() -> list[dict]:
    """Scrape NYS Contract Reporter for open solicitations."""
    log.info("Scraping New York NYSCR...")
    rfps: list[dict] = []

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
    })

    try:
        for page_num in range(1, NY_NYSCR_MAX_PAGES + 1):
            resp = session.get(
                "https://www.nyscr.ny.gov/Ads/IframeSearch",
                params={"page": page_num},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for listing blocks or table rows
            listings = soup.find_all(
                "div",
                class_=lambda c: c and ("listing" in c or "ad-" in c or "result" in c),
            )

            if not listings:
                # Try links to ad detail pages
                listings = soup.find_all(
                    "a", href=lambda h: h and "/Ads/" in h and "Detail" in h
                )

            if not listings:
                # Fallback: table rows
                table = soup.find("table")
                if table:
                    for row in table.find_all("tr")[1:]:
                        cells = row.find_all("td")
                        if not cells or len(cells) < 3:
                            continue
                        link = row.find("a", href=True)
                        href = link.get("href", "") if link else ""
                        title = link.get_text(strip=True) if link else cells[0].get_text(strip=True)
                        sol_id = cells[0].get_text(strip=True) if cells else ""

                        if title and len(title) > 5:
                            full_url = href
                            if href and not href.startswith("http"):
                                full_url = f"https://www.nyscr.ny.gov{href}"
                            rfps.append({
                                "state": "NY",
                                "source": "NY NYSCR",
                                "id": sol_id,
                                "title": title,
                                "agency": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                                "status": "Open",
                                "posted_date": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                                "close_date": cells[3].get_text(strip=True) if len(cells) > 3 else "",
                                "url": full_url,
                                "description": title,
                                "amount": "",
                            })
                else:
                    # Last resort: all links that look like ad detail pages
                    for link in soup.find_all("a", href=True):
                        href = link.get("href", "")
                        text = link.get_text(strip=True)
                        if ("/Ads/" in href or "/ads/" in href) and text and len(text) > 10:
                            full_url = href if href.startswith("http") else f"https://www.nyscr.ny.gov{href}"
                            rfps.append({
                                "state": "NY",
                                "source": "NY NYSCR",
                                "id": "",
                                "title": text,
                                "agency": "",
                                "status": "Open",
                                "posted_date": "",
                                "close_date": "",
                                "url": full_url,
                                "description": text,
                                "amount": "",
                            })
            else:
                for item in listings:
                    text = item.get_text(strip=True) if hasattr(item, "get_text") else str(item)
                    link = item.find("a", href=True) if hasattr(item, "find") else item
                    href = link.get("href", "") if link else ""
                    title = link.get_text(strip=True) if link and hasattr(link, "get_text") else text[:200]

                    if title and len(title) > 5:
                        full_url = href if href.startswith("http") else f"https://www.nyscr.ny.gov{href}" if href else ""
                        rfps.append({
                            "state": "NY",
                            "source": "NY NYSCR",
                            "id": "",
                            "title": title,
                            "agency": "",
                            "status": "Open",
                            "posted_date": "",
                            "close_date": "",
                            "url": full_url,
                            "description": title[:500],
                            "amount": "",
                        })

            time.sleep(POLITE_DELAY)

    except requests.RequestException as e:
        log.error(f"NY NYSCR scrape failed: {e}")

    log.info(f"NY NYSCR total: {len(rfps)} solicitations")
    return rfps
