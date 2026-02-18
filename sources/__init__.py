"""All source scrapers for the research scraper."""

from sources.sam_gov import scrape_sam_gov
from sources.grants_gov import scrape_grants_gov
from sources.socrata import scrape_socrata
from sources.texas_esbd import scrape_texas_esbd
from sources.nc_evp import scrape_nc_evp
from sources.bidnet import scrape_bidnet

ALL_SOURCES = [
    scrape_sam_gov,
    scrape_grants_gov,
    scrape_socrata,
    scrape_texas_esbd,
    scrape_nc_evp,
    scrape_bidnet,
]
