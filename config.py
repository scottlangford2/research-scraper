"""
Configuration, paths, and logging setup for the research scraper.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
LOG_DIR = SCRIPT_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

PARQUET_FILE = DATA_DIR / "rfps.parquet"
SEEN_FILE = DATA_DIR / "seen_hashes.json"

# ---------------------------------------------------------------------------
# Environment — try local .env, fall back to sibling scraper's .env
# ---------------------------------------------------------------------------

_env_path = SCRIPT_DIR / ".env"
if not _env_path.exists():
    _env_path = SCRIPT_DIR.parent / "scraper" / ".env"
load_dotenv(_env_path)

SAM_GOV_API_KEY = os.getenv("SAM_GOV_API_KEY", "")

# ---------------------------------------------------------------------------
# Scraping constants
# ---------------------------------------------------------------------------

SAM_LOOKBACK_DAYS = 30
GRANTS_ROWS_PER_QUERY = 100
SOCRATA_LOOKBACK_DAYS = 30
ESBD_MAX_PAGES = 20
BIDNET_MAX_PAGES_PER_STATE = 8  # increased from 5 to capture more local listings
NC_EVP_MAX_PAGES = 30
REQUEST_TIMEOUT = 30
POLITE_DELAY = 1  # seconds between paginated requests
PLAYWRIGHT_TIMEOUT = 60000  # ms

# Local aggregator limits
DEMANDSTAR_MAX_PAGES = 5

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"research_scraper_{today}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("research_scraper")


log = setup_logging()
