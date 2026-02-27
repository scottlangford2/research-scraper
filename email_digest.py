"""
Email digest module for the research scraper.

Sends two types of email:
  - Daily digest: all keyword-matched RFPs from today's scrape → EMAIL_TO
  - Team digest: past 7 days of matches, filtered per team member → individual emails
"""

import re
import smtplib
from collections import defaultdict
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pyarrow.parquet as pq

from config import (
    PARQUET_FILE, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
    EMAIL_FROM, EMAIL_TO, log,
)

# Render order for state grouping in email tables
_GROUP_ORDER = [
    "Federal", "TX", "NY", "CA", "FL", "IL", "PA", "OH", "GA", "NC",
    "MI", "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD",
]

_STATE_LABELS = {
    "Federal": "Federal", "TX": "Texas", "NY": "New York", "CA": "California",
    "FL": "Florida", "IL": "Illinois", "PA": "Pennsylvania", "OH": "Ohio",
    "GA": "Georgia", "NC": "North Carolina", "MI": "Michigan", "NJ": "New Jersey",
    "VA": "Virginia", "WA": "Washington", "AZ": "Arizona", "MA": "Massachusetts",
    "TN": "Tennessee", "IN": "Indiana", "MO": "Missouri", "MD": "Maryland",
}


# ---------------------------------------------------------------------------
# SMTP helpers
# ---------------------------------------------------------------------------

def _get_smtp_config() -> dict | None:
    """Load SMTP configuration. Returns None if not configured."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS]):
        log.warning("Email not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASS in .env.")
        return None
    return {
        "host": SMTP_HOST, "port": SMTP_PORT,
        "user": SMTP_USER, "password": SMTP_PASS, "from": EMAIL_FROM,
    }


def _send_one_email(smtp_cfg: dict, to_addr: str, subject: str,
                     html_body: str, text_body: str):
    """Send a single email via SMTP with STARTTLS."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_cfg["from"]
    msg["To"] = to_addr
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"]) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_cfg["user"], smtp_cfg["password"])
        server.sendmail(smtp_cfg["from"], [to_addr], msg.as_string())


# ---------------------------------------------------------------------------
# HTML / plain-text builders
# ---------------------------------------------------------------------------

def _build_tables_html(rfps: list[dict]) -> str:
    """Build HTML tables grouped by state."""
    groups: dict[str, list] = defaultdict(list)
    for r in rfps:
        groups[r["state"]].append(r)

    render_order = list(_GROUP_ORDER)
    for key in sorted(groups.keys()):
        if key not in render_order:
            render_order.append(key)

    parts: list[str] = []
    for state_key in render_order:
        group = groups.get(state_key, [])
        if not group:
            continue
        label = _STATE_LABELS.get(state_key, state_key)
        parts.append(f"<h3>{label} ({len(group)})</h3>")
        parts.append(
            "<table border='1' cellpadding='6' cellspacing='0' "
            "style='border-collapse:collapse; font-size:13px;'>"
        )
        parts.append(
            "<tr style='background:#f0f0f0;'>"
            "<th>ID</th><th>Title</th><th>Agency</th>"
            "<th>Status</th><th>Posted</th><th>Closes</th><th>Link</th></tr>"
        )
        for r in group:
            link = f"<a href='{r['url']}'>View</a>" if r.get("url") else "\u2014"
            parts.append(
                f"<tr>"
                f"<td>{r.get('rfp_id', '\u2014')}</td>"
                f"<td>{r.get('title', '\u2014')}</td>"
                f"<td>{r.get('agency', '\u2014')}</td>"
                f"<td>{r.get('status', '\u2014')}</td>"
                f"<td>{r.get('posted_date', '\u2014')}</td>"
                f"<td>{r.get('close_date', '\u2014')}</td>"
                f"<td>{link}</td>"
                f"</tr>"
            )
        parts.append("</table>")
    return "\n".join(parts)


def _build_plain_text(rfps: list[dict]) -> str:
    """Build plain-text listing."""
    lines: list[str] = []
    for r in rfps:
        lines.append(
            f"[{r['state']}] {r.get('title', 'Untitled')}\n"
            f"  ID: {r.get('rfp_id', '\u2014')}  |  Agency: {r.get('agency', '\u2014')}\n"
            f"  Status: {r.get('status', '\u2014')}  |  Closes: {r.get('close_date', '\u2014')}\n"
            f"  {r.get('url', '')}\n"
        )
    return "\n".join(lines)


def _summary_counts(rfps: list[dict]) -> str:
    """Build a summary string like '5 Federal, 3 Texas'."""
    groups: dict[str, int] = defaultdict(int)
    for r in rfps:
        groups[r["state"]] += 1
    parts: list[str] = []
    for key in _GROUP_ORDER:
        if key in groups:
            parts.append(f"{groups[key]} {_STATE_LABELS.get(key, key)}")
    for key in sorted(groups.keys()):
        if key not in _GROUP_ORDER:
            parts.append(f"{groups[key]} {key}")
    return ", ".join(parts) if parts else "0"


# ---------------------------------------------------------------------------
# Parquet readers
# ---------------------------------------------------------------------------

def _read_today_matches() -> list[dict]:
    """Read today's keyword-matched RFPs from Parquet."""
    if not PARQUET_FILE.exists():
        return []
    table = pq.read_table(PARQUET_FILE)
    df = table.to_pandas()
    today = datetime.now().strftime("%Y-%m-%d")
    matched = df[(df["scrape_date"] == today) & (df["keyword_match"] == True)]
    return matched.to_dict("records")


def _read_week_matches() -> list[dict]:
    """Read past 7 days of keyword-matched RFPs from Parquet."""
    if not PARQUET_FILE.exists():
        return []
    table = pq.read_table(PARQUET_FILE)
    df = table.to_pandas()
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    matched = df[(df["scrape_date"] >= cutoff) & (df["keyword_match"] == True)]
    return matched.to_dict("records")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_FEEDBACK_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSfug2oiGoHbVZf-Qml8B01M8kcmmNhy4Jm1VBWd3rJyU__ceQ/viewform?usp=header"
)
_DASHBOARD_URL = "https://scottlangford2.github.io/research-scraper/"
_GITHUB_URL = "https://github.com/scottlangford2/research-scraper"


def send_daily_email():
    """Send the daily catch-all digest to EMAIL_TO."""
    if not EMAIL_TO:
        log.warning("EMAIL_TO not set in .env. Skipping daily email.")
        return

    smtp_cfg = _get_smtp_config()
    if not smtp_cfg:
        return

    rfps = _read_today_matches()
    if not rfps:
        log.info("No keyword matches today. Skipping daily email.")
        return

    today = datetime.now().strftime("%B %d, %Y")
    subject = f"RFP Alert: {len(rfps)} New Matches \u2014 {today}"
    summary = _summary_counts(rfps)

    html = (
        "<html><body style='font-family:Arial,sans-serif;'>"
        f"<h2>Daily RFP Summary \u2014 {today}</h2>"
        f"<p><strong>{len(rfps)} new RFPs</strong> matching your keywords "
        f"({summary}).</p>"
        + _build_tables_html(rfps)
        + "<hr>"
        f"<p style='margin-top:16px;'>"
        f"<a href='{_FEEDBACK_URL}' "
        f"style='background-color:#4285f4;color:#fff;padding:8px 16px;"
        f"text-decoration:none;border-radius:4px;font-size:13px;'>"
        f"Share Feedback</a></p>"
        "<p style='color:#888;font-size:11px;'>"
        f"<a href='{_DASHBOARD_URL}' style='color:#888;'>Dashboard</a>"
        f" &middot; "
        f"<a href='{_GITHUB_URL}' style='color:#888;'>GitHub</a>"
        f"<br>Generated by Lookout Analytics RFP Scraper</p>"
        "</body></html>"
    )
    text = (
        f"Daily RFP Summary \u2014 {today}\n{len(rfps)} new matches\n\n"
        + _build_plain_text(rfps)
        + f"\n---\nShare feedback: {_FEEDBACK_URL}\n"
        + f"Dashboard: {_DASHBOARD_URL}\n"
        + f"GitHub: {_GITHUB_URL}\n"
    )

    try:
        _send_one_email(smtp_cfg, EMAIL_TO, subject, html, text)
        log.info(f"Daily email sent to {EMAIL_TO} with {len(rfps)} RFPs")
    except Exception as e:
        log.error(f"Failed to send daily email to {EMAIL_TO}: {e}")


def send_team_digest():
    """Send personalized weekly digest to each team member.

    Each person receives only the RFPs matching their specific keyword
    patterns from the past 7 days.
    """
    try:
        from team_config import TEAM_MEMBERS
    except ImportError:
        log.warning("team_config.py not found. Skipping team digest.")
        return

    smtp_cfg = _get_smtp_config()
    if not smtp_cfg:
        return

    all_rfps = _read_week_matches()
    if not all_rfps:
        log.info("No keyword matches in past 7 days. Skipping team digest.")
        return

    today = datetime.now().strftime("%B %d, %Y")
    log.info(f"Sending team digest to {len(TEAM_MEMBERS)} members ({len(all_rfps)} matched RFPs)...")

    for member in TEAM_MEMBERS:
        # Compile member's keyword pattern
        pattern = re.compile(
            "|".join(re.escape(p) for p in member["patterns"]),
            re.IGNORECASE,
        )

        # Filter RFPs to this person's interests
        personal_rfps = []
        for rfp in all_rfps:
            text = " ".join([
                rfp.get("title", ""),
                rfp.get("description", ""),
                rfp.get("agency", ""),
            ])
            if pattern.search(text):
                personal_rfps.append(rfp)

        if not personal_rfps:
            log.info(f"  {member['name']}: 0 matches, skipping")
            continue

        first_name = member["name"].split()[0]
        subject = (
            f"Weekly RFP Digest: {len(personal_rfps)} Matches "
            f"for {first_name} \u2014 {today}"
        )
        summary = _summary_counts(personal_rfps)

        html = (
            "<html><body style='font-family:Arial,sans-serif;'>"
            f"<h2>Weekly RFP Digest \u2014 {today}</h2>"
            f"<p>Hi {first_name},</p>"
            f"<p><strong>{len(personal_rfps)} RFPs</strong> matching your "
            f"research interests ({summary}).</p>"
            + _build_tables_html(personal_rfps)
            + "<hr>"
            f"<p style='margin-top:16px;'>"
            f"<a href='{_FEEDBACK_URL}' "
            f"style='background-color:#4285f4;color:#fff;padding:8px 16px;"
            f"text-decoration:none;border-radius:4px;font-size:13px;'>"
            f"Share Feedback</a></p>"
            "<p style='color:#888;font-size:11px;'>"
            f"<a href='{_DASHBOARD_URL}' style='color:#888;'>Dashboard</a>"
            f" &middot; "
            f"<a href='{_GITHUB_URL}' style='color:#888;'>GitHub</a>"
            f"<br>"
            "Generated by Lookout Analytics RFP Scraper \u2014 "
            "Texas State University Team<br>"
            f"Your keyword domains: {', '.join(member['patterns'][:6])}, ...</p>"
            f"<p style='color:#999;font-size:10px;margin-top:12px;'>"
            f"<a href='mailto:scottlangford@txstate.edu"
            f"?subject=Unsubscribe%20from%20RFP%20Digest"
            f"&body=Please%20remove%20{member['name'].replace(' ', '%20')}"
            f"%20({member['email']})%20from%20the%20weekly%20RFP%20digest.' "
            f"style='color:#999;'>Unsubscribe</a></p>"
            "</body></html>"
        )
        text = (
            f"Weekly RFP Digest \u2014 {today}\n"
            f"Hi {first_name},\n\n"
            f"{len(personal_rfps)} RFPs matching your interests\n\n"
            + _build_plain_text(personal_rfps)
            + f"\n---\nShare feedback: {_FEEDBACK_URL}\n"
            + f"Dashboard: {_DASHBOARD_URL}\n"
            + f"GitHub: {_GITHUB_URL}\n"
            + "To unsubscribe: email scottlangford@txstate.edu with subject \"Unsubscribe\"\n"
        )

        try:
            _send_one_email(smtp_cfg, member["email"], subject, html, text)
            log.info(f"  {member['name']} ({member['email']}): {len(personal_rfps)} RFPs sent")
        except Exception as e:
            log.error(f"  Failed to send to {member['name']} ({member['email']}): {e}")
