"""All source scrapers for the research scraper."""

from sources.sam_gov import scrape_sam_gov
from sources.grants_gov import scrape_grants_gov
from sources.socrata import scrape_socrata
from sources.texas_esbd import scrape_texas_esbd
from sources.nc_evp import scrape_nc_evp
from sources.bidnet import scrape_bidnet
from sources.buyspeed import scrape_buyspeed
from sources.jaggaer import scrape_jaggaer
from sources.state_portals import scrape_state_portals
from sources.demandstar import scrape_demandstar

ALL_SOURCES = [
    # Federal
    scrape_sam_gov,
    scrape_grants_gov,
    # Aggregators (state + local)
    scrape_socrata,
    scrape_bidnet,
    scrape_demandstar,
    # Dedicated state scrapers
    scrape_texas_esbd,
    scrape_nc_evp,
    # Platform-grouped state scrapers
    scrape_buyspeed,       # AR, IL, MA, NV, NJ, OR
    scrape_jaggaer,        # GA, IA, MT, NM, PA, UT
    # Individual state portals (all remaining states)
    scrape_state_portals,
]
