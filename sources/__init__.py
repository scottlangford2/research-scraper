"""Federal source scrapers (Phase 1)."""

from sources.sam_gov import scrape_sam_gov
from sources.grants_gov import scrape_grants_gov

ALL_SOURCES = [
    scrape_sam_gov,
    scrape_grants_gov,
]
