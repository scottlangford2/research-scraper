#!/bin/bash
# ============================================================
# Desktop Setup Script — Research RFP Scraper
# ============================================================
# Run this on the desktop Mac after installing Python 3.13:
#   https://www.python.org/downloads/
#
# Usage:
#   cd "/Users/scottlangford/Library/CloudStorage/Dropbox/Lookout Analytics/research_scraper"
#   bash setup_desktop.sh
# ============================================================

set -e

PYTHON="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "=== Research Scraper Desktop Setup ==="
echo ""

# 1. Check Python 3.13
if [ ! -f "$PYTHON" ]; then
    echo "ERROR: Python 3.13 not found at $PYTHON"
    echo "Download from: https://www.python.org/downloads/"
    exit 1
fi
echo "Python: $($PYTHON --version)"

# 2. Install packages
echo ""
echo "Installing Python packages..."
$PYTHON -m pip install --upgrade pip
$PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt"

# 3. Install Playwright browser
echo ""
echo "Installing Playwright Chromium..."
$PYTHON -m playwright install chromium

# 4. Copy and load launchd plists
echo ""
echo "Setting up scheduled jobs..."
mkdir -p "$LAUNCH_AGENTS"

for plist in "$SCRIPT_DIR/launchd/"*.plist; do
    name=$(basename "$plist")
    # Unload if already loaded
    launchctl unload "$LAUNCH_AGENTS/$name" 2>/dev/null || true
    # Copy and load
    cp "$plist" "$LAUNCH_AGENTS/$name"
    launchctl load "$LAUNCH_AGENTS/$name"
    echo "  Loaded: $name"
done

# 5. Verify
echo ""
echo "=== Verification ==="
echo "Loaded jobs:"
launchctl list | grep lookoutanalytics || echo "  (none found)"
echo ""
echo "Quick import test..."
cd "$SCRIPT_DIR"
$PYTHON -c "
from sources import ALL_SOURCES
from email_digest import send_daily_email, send_team_digest
from team_config import TEAM_MEMBERS
print(f'  {len(ALL_SOURCES)} scrapers, {len(TEAM_MEMBERS)} team members — OK')
"

echo ""
echo "=== Setup complete ==="
echo "Schedule:"
echo "  12:01 AM  — Scrape all 17 sources + update dashboard"
echo "   6:00 AM  — Send daily digest email"
echo "  Mon 6 AM  — Send weekly team digest emails"
