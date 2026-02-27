"""All source scrapers for the research scraper."""

from sources.sam_gov import scrape_sam_gov
from sources.grants_gov import scrape_grants_gov
from sources.sbir import scrape_sbir
from sources.nih_reporter import scrape_nih_reporter
from sources.nsf_awards import scrape_nsf_awards
from sources.federal_register import scrape_federal_register
from sources.usaspending import scrape_usaspending
from sources.propublica import scrape_propublica
from sources.socrata import scrape_socrata
from sources.texas_esbd import scrape_texas_esbd
from sources.nc_evp import scrape_nc_evp
from sources.ny_nyscr import scrape_ny_nyscr
from sources.bidnet import scrape_bidnet
from sources.buyspeed import scrape_buyspeed
from sources.jaggaer import scrape_jaggaer
from sources.state_portals import scrape_state_portals
from sources.demandstar import scrape_demandstar

ALL_SOURCES = [
    # Federal
    scrape_sam_gov,
    scrape_grants_gov,
    scrape_sbir,
    scrape_nih_reporter,
    scrape_nsf_awards,
    scrape_federal_register,
    scrape_usaspending,
    scrape_propublica,
    # Aggregators (state + local)
    scrape_socrata,
    scrape_bidnet,
    scrape_demandstar,
    # Dedicated state scrapers
    scrape_texas_esbd,
    scrape_nc_evp,
    scrape_ny_nyscr,
    # Platform-grouped state scrapers
    scrape_buyspeed,       # AR, IL, MA, NV, NJ, OR
    scrape_jaggaer,        # GA, IA, MT, NM, PA, UT
    # Individual state portals (all remaining states)
    scrape_state_portals,
]
