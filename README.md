# Research RFP Scraper

Automated pipeline that aggregates federal, state, and local procurement opportunities from 17 sources across all 50 states. Classifies RFPs by research keywords, extracts key terms via NLP, and delivers daily email digests and personalized weekly summaries to team members.

## Sources (17)

### Federal (8)

| Source | Method |
|--------|--------|
| SAM.gov | REST API (key required) |
| Grants.gov | REST API |
| SBIR.gov | REST API |
| NIH RePORTER | REST API |
| NSF Awards | REST API |
| Federal Register | REST API |
| USAspending.gov | REST API |
| ProPublica Nonprofits | REST API |

### State & Local (9)

| Source | Coverage | Method |
|--------|----------|--------|
| Socrata | MD, NY, TX, WA | SODA API |
| BidNet | All 50 states | Playwright |
| DemandStar | All 50 states | Playwright |
| BuySpeed | AR, IL, MA, NV, NJ, OR | Playwright |
| JAGGAER | GA, IA, MT, NM, PA, UT | Playwright |
| State Portals | 43 states | Playwright |
| Texas ESBD | TX | HTML scrape |
| North Carolina eVP | NC | Playwright |
| New York NYSCR | NY | HTML scrape |

## Quick Start

```bash
# 1. Install dependencies
pip3 install -r requirements.txt
python3 -m playwright install chromium

# 2. Configure environment
cp .env.template .env
# Edit .env with SMTP credentials and (optionally) SAM.gov API key

# 3. Configure team members
cp team_config.template.py team_config.py
# Edit team_config.py with names, emails, and keyword patterns

# 4. Run
python3 main.py                # full scrape + dashboard
python3 main.py --daily-email  # send daily digest
python3 main.py --team-digest  # send personalized weekly digests
```

## Scheduling (macOS)

Three LaunchAgent plists in `launchd/`:

| Plist | Schedule | Mode |
|-------|----------|------|
| `researchscraper.plist` | Daily 12:01 AM | Full scrape + dashboard |
| `researchscraper.email.plist` | Daily 6:00 AM | Daily email digest |
| `researchscraper.monday.plist` | Monday 6:00 AM | Daily + team digests |

Install with `setup_desktop.sh` or manually:

```bash
cp launchd/*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.lookoutanalytics.researchscraper.plist
launchctl load ~/Library/LaunchAgents/com.lookoutanalytics.researchscraper.email.plist
launchctl load ~/Library/LaunchAgents/com.lookoutanalytics.researchscraper.monday.plist
```

## Configuration

### Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `SMTP_HOST` | Yes | SMTP server (e.g., `smtp.gmail.com`) |
| `SMTP_PORT` | Yes | SMTP port (typically `587`) |
| `SMTP_USER` | Yes | SMTP login email |
| `SMTP_PASS` | Yes | SMTP password or app password |
| `EMAIL_TO` | Yes | Daily summary recipient |
| `EMAIL_FROM` | No | Sender display (defaults to `SMTP_USER`) |
| `SAM_GOV_API_KEY` | No | SAM.gov API key (expires every 90 days) |
| `HISTORICAL_MODE` | No | Set to `true` for one-time backfill |

### Team Members (`team_config.py`)

Each entry defines a team member who receives a personalized Monday digest:

```python
TEAM_MEMBERS = [
    {
        "name": "Jane Doe",
        "email": "jdoe@university.edu",
        "patterns": [
            "economic development", "fiscal analysis",
            "cost-benefit", "impact study",
        ],
    },
]
```

## Pipeline

1. **Scrape** all 17 sources
2. **Deduplicate** via SHA-256 hash (`state-id-title`)
3. **Classify** against 226 keyword phrases (deductive)
4. **Extract** key terms via RAKE NLP (inductive)
5. **Analyze** corpus-level keyword frequencies (TF-IDF)
6. **Generate** HTML dashboard with state coverage map
7. **Push** dashboard to GitHub Pages

## Output

### Parquet Dataset (`data/rfps.parquet`)

| Column | Description |
|--------|-------------|
| `rfp_id` | Source-specific identifier |
| `hash` | SHA-256 dedup key |
| `source` | Origin (e.g., SAM.gov, BidNet) |
| `state` | State or "Federal" |
| `title` | Opportunity title |
| `agency` | Issuing organization |
| `posted_date` / `close_date` | Posting and deadline dates |
| `url` | Link to full listing |
| `amount` | Dollar value (when available) |
| `keyword_match` | Boolean: matches research keywords |
| `matched_keywords` | Which keywords matched |
| `key_terms` | NLP-extracted salient terms |

## Project Structure

```
main.py                     # Pipeline orchestrator
config.py                   # Paths, constants, env loading
filters.py                  # 226 keyword phrases + classification
keywords.py                 # RAKE-based key term extraction
storage.py                  # Parquet I/O + SHA-256 dedup
email_digest.py             # Daily + team email formatting/sending
analyze_keywords.py         # Corpus-level TF-IDF analysis
generate_site.py            # HTML dashboard + GitHub Pages push
team_config.py              # Team members (gitignored)
sources/                    # 17 scraper modules
  sam_gov.py, grants_gov.py, sbir.py, nih_reporter.py,
  nsf_awards.py, federal_register.py, usaspending.py,
  propublica.py, socrata.py, texas_esbd.py, nc_evp.py,
  ny_nyscr.py, bidnet.py, buyspeed.py, jaggaer.py,
  state_portals.py, demandstar.py
launchd/                    # macOS LaunchAgent plists
data/                       # Runtime: rfps.parquet, seen_hashes.json
logs/                       # Runtime: daily log files
```

## License

Private repository. All rights reserved.
