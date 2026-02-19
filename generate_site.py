#!/usr/bin/env python3
"""
GitHub Pages / local dashboard generator for the research scraper.

Reads the Parquet dataset and keyword analysis data, extracts summary
statistics, and renders a static HTML dashboard into docs/index.html.

Called from main.py at the end of each scrape run.
Can also be run standalone: python generate_site.py
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from config import PARQUET_FILE, DATA_DIR, SCRIPT_DIR, log

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DOCS_DIR = SCRIPT_DIR / "docs"
DOCS_DATA_DIR = DOCS_DIR / "data"
SUMMARY_JSON = DOCS_DATA_DIR / "summary.json"
INDEX_HTML = DOCS_DIR / "index.html"
TOP_TERMS_FILE = DATA_DIR / "top_terms.json"
US_MAP_SVG = DOCS_DIR / "us_map.svg"

# US Census 2024 estimates (population in millions)
STATE_POPULATIONS = {
    "AL": 5.14, "AK": 0.74, "AZ": 7.58, "AR": 3.07, "CA": 38.97,
    "CO": 5.91, "CT": 3.62, "DE": 1.03, "FL": 22.97, "GA": 11.10,
    "HI": 1.44, "ID": 2.04, "IL": 12.55, "IN": 6.90, "IA": 3.22,
    "KS": 2.95, "KY": 4.54, "LA": 4.60, "ME": 1.40, "MD": 6.24,
    "MA": 7.11, "MI": 10.04, "MN": 5.77, "MS": 2.94, "MO": 6.21,
    "MT": 1.14, "NE": 2.00, "NV": 3.28, "NH": 1.41, "NJ": 9.50,
    "NM": 2.13, "NY": 19.57, "NC": 10.87, "ND": 0.79, "OH": 11.78,
    "OK": 4.05, "OR": 4.24, "PA": 12.96, "RI": 1.10, "SC": 5.45,
    "SD": 0.92, "TN": 7.13, "TX": 30.86, "UT": 3.47, "VT": 0.65,
    "VA": 8.72, "WA": 7.91, "WV": 1.77, "WI": 5.91, "WY": 0.58,
}


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def build_summary_data() -> dict:
    """Extract all summary statistics from the Parquet dataset."""
    table = pq.read_table(PARQUET_FILE)
    df = table.to_pandas()

    now = datetime.now()
    summary = {}

    # --- Overview metrics ---
    summary["generated"] = now.strftime("%Y-%m-%d %H:%M:%S")
    summary["total_rfps"] = int(len(df))
    summary["keyword_matches"] = int(df["keyword_match"].sum())
    summary["states_covered"] = int(df["state"].nunique())
    summary["sources_active"] = int(df["source"].nunique())

    # Latest scrape date
    if "scrape_date" in df.columns:
        summary["scrape_date"] = str(df["scrape_date"].max())
    else:
        summary["scrape_date"] = now.strftime("%Y-%m-%d")

    # --- State breakdown ---
    state_stats = (
        df.groupby("state")
        .agg(
            total=("keyword_match", "count"),
            matches=("keyword_match", "sum"),
        )
        .assign(match_rate=lambda x: round(x["matches"] / x["total"] * 100, 1))
        .sort_values("total", ascending=False)
    )
    summary["states"] = [
        {
            "state": str(state),
            "total": int(row["total"]),
            "matches": int(row["matches"]),
            "match_rate": float(row["match_rate"]),
            "per_capita": round(
                int(row["total"]) / STATE_POPULATIONS.get(str(state), 1.0), 1
            ) if str(state) in STATE_POPULATIONS else 0,
        }
        for state, row in state_stats.iterrows()
    ]

    # --- Source performance ---
    source_stats = (
        df.groupby("source")
        .agg(
            total=("keyword_match", "count"),
            matches=("keyword_match", "sum"),
        )
        .sort_values("total", ascending=False)
    )
    summary["sources"] = [
        {
            "source": str(source),
            "total": int(row["total"]),
            "matches": int(row["matches"]),
        }
        for source, row in source_stats.iterrows()
    ]

    # --- Keyword analysis from top_terms.json ---
    if TOP_TERMS_FILE.exists():
        with open(TOP_TERMS_FILE) as f:
            top_terms = json.load(f)

        tfidf = top_terms.get("top_tfidf", {})
        summary["top_tfidf"] = [
            {"term": str(term), "score": round(float(score), 6)}
            for term, score in sorted(tfidf.items(), key=lambda x: -x[1])[:20]
        ]

        gap = top_terms.get("gap_terms", {})
        summary["gap_terms"] = [
            {"term": str(term), "score": round(float(score), 6)}
            for term, score in sorted(gap.items(), key=lambda x: -x[1])[:15]
        ]

        summary["rake_phrases"] = [
            str(p) for p in top_terms.get("rake_phrases", [])[:15]
        ]
    else:
        summary["top_tfidf"] = []
        summary["gap_terms"] = []
        summary["rake_phrases"] = []

    # --- Full database (all RFPs, sorted by recency) ---
    full_df = df.copy()
    if "scrape_timestamp" in full_df.columns:
        full_df = full_df.sort_values("scrape_timestamp", ascending=False)

    summary["full_database"] = [
        {
            "title": str(row.get("title", ""))[:120],
            "state": str(row.get("state", "")),
            "agency": str(row.get("agency", ""))[:80],
            "url": str(row.get("url", "")),
            "source": str(row.get("source", "")),
            "posted_date": str(row.get("posted_date", "") or ""),
            "close_date": str(row.get("close_date", "") or ""),
            "amount": str(row.get("amount", "") or ""),
            "keyword_match": bool(row.get("keyword_match", False)),
        }
        for _, row in full_df.iterrows()
    ]

    # --- Daily counts time series ---
    if "scrape_date" in df.columns:
        daily = (
            df.groupby("scrape_date")
            .agg(
                total=("keyword_match", "count"),
                matches=("keyword_match", "sum"),
            )
            .sort_index()
        )
        # Cumulative totals over time
        cumulative_total = 0
        cumulative_matches = 0
        daily_series = []
        for date, row in daily.iterrows():
            cumulative_total += int(row["total"])
            cumulative_matches += int(row["matches"])
            daily_series.append({
                "date": str(date),
                "new_rfps": int(row["total"]),
                "new_matches": int(row["matches"]),
                "cumulative_rfps": cumulative_total,
                "cumulative_matches": cumulative_matches,
            })
        summary["daily_counts"] = daily_series
    else:
        summary["daily_counts"] = []

    # --- Top matched keyword frequency ---
    matched_df = df[df["keyword_match"] == True]
    all_kw: list[str] = []
    for kws in matched_df["matched_keywords"].dropna():
        all_kw.extend([k.strip() for k in str(kws).split(",") if k.strip()])
    kw_counts: dict[str, int] = {}
    for kw in all_kw:
        kw_counts[kw] = kw_counts.get(kw, 0) + 1
    summary["keyword_frequency"] = sorted(
        [{"keyword": k, "count": v} for k, v in kw_counts.items()],
        key=lambda x: -x["count"],
    )[:20]

    return summary


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def render_html(summary: dict):
    """Write docs/index.html and docs/data/summary.json."""
    DOCS_DIR.mkdir(exist_ok=True)
    DOCS_DATA_DIR.mkdir(exist_ok=True)

    # Write JSON (useful for programmatic access)
    with open(SUMMARY_JSON, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Build HTML with inlined JSON data
    json_blob = json.dumps(summary, default=str)
    html = _build_html(json_blob)
    INDEX_HTML.write_text(html, encoding="utf-8")

    size_kb = SUMMARY_JSON.stat().st_size / 1024
    log.info(f"Site generated: {INDEX_HTML} ({size_kb:.1f} KB data)")


def _build_html(json_blob: str) -> str:
    """Construct the full HTML page with embedded data."""

    # Load SVG map if available
    svg_map = ""
    if US_MAP_SVG.exists():
        svg_map = US_MAP_SVG.read_text(encoding="utf-8")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research RFP Scraper &mdash; Dashboard</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>

<header>
    <h1>Research RFP Scraper</h1>
    <div class="subtitle" id="last-updated">Loading...</div>
</header>

<main>

    <!-- Overview Cards -->
    <section>
        <h2 class="section-title">Overview</h2>
        <div class="cards">
            <div class="card">
                <div class="label">Total RFPs</div>
                <div class="value" id="total-rfps">--</div>
            </div>
            <div class="card">
                <div class="label">Keyword Matches</div>
                <div class="value green" id="keyword-matches">--</div>
            </div>
            <div class="card">
                <div class="label">States Covered</div>
                <div class="value" id="states-covered">--</div>
            </div>
            <div class="card">
                <div class="label">Active Sources</div>
                <div class="value" id="sources-active">--</div>
            </div>
            <div class="card">
                <div class="label">Latest Scrape</div>
                <div class="value accent" id="scrape-date" style="font-size:1.2rem">--</div>
            </div>
        </div>
    </section>

    <!-- Per-Capita Map -->
    <section>
        <h2 class="section-title">RFPs Per Capita by State</h2>
        <div class="map-container">
            <div class="map-wrap" id="map-wrap">
                {svg_map}
            </div>
            <div class="map-legend" id="map-legend"></div>
            <div class="map-tooltip" id="map-tooltip"></div>
        </div>
    </section>

    <!-- RFPs Over Time -->
    <section>
        <h2 class="section-title">RFPs Over Time</h2>
        <div class="chart-container">
            <div class="chart-toggle">
                <button class="chart-btn active" data-mode="cumulative">Cumulative</button>
                <button class="chart-btn" data-mode="daily">Daily New</button>
            </div>
            <canvas id="line-chart" height="300"></canvas>
        </div>
    </section>

    <!-- State Breakdown -->
    <section>
        <h2 class="section-title">RFPs by State</h2>
        <div class="two-col">
            <div class="bar-chart" id="state-bars" style="max-height: 600px; overflow-y: auto;"></div>
            <div class="table-wrap" style="max-height: 600px; overflow-y: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>State</th>
                            <th>RFPs</th>
                            <th>Matches</th>
                            <th>Rate</th>
                        </tr>
                    </thead>
                    <tbody id="state-table-body"></tbody>
                </table>
            </div>
        </div>
    </section>

    <!-- Source Performance -->
    <section>
        <h2 class="section-title">Source Performance</h2>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>RFPs</th>
                        <th>Matches</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="source-table-body"></tbody>
            </table>
        </div>
    </section>

    <!-- Keyword Analysis -->
    <section>
        <h2 class="section-title">Keyword Analysis</h2>
        <div class="three-col">
            <div>
                <div class="bar-chart">
                    <h3 style="font-size:0.9rem; color:var(--navy); margin-bottom:0.75rem;">
                        Top TF-IDF Terms (Corpus-wide)
                    </h3>
                    <div id="tfidf-bars"></div>
                </div>
            </div>
            <div>
                <div class="bar-chart">
                    <h3 style="font-size:0.9rem; color:var(--navy); margin-bottom:0.75rem;">
                        Most Common Matched Keywords
                    </h3>
                    <div id="keyword-freq-bars"></div>
                </div>
            </div>
            <div>
                <div class="pill-list">
                    <h3>Gap Candidates (not in keyword list)</h3>
                    <div id="gap-terms"></div>
                </div>
                <div class="pill-list" style="margin-top:1rem;">
                    <h3>Top RAKE Phrases</h3>
                    <div id="rake-phrases"></div>
                </div>
            </div>
        </div>
    </section>

    <!-- Full Database -->
    <section>
        <h2 class="section-title">Full Database</h2>
        <div style="margin-bottom:0.75rem; display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center;">
            <input type="text" id="db-search" placeholder="Search titles, agencies, states..."
                   style="padding:0.4rem 0.75rem; border:1px solid var(--gray-300); border-radius:6px;
                          font-size:0.85rem; width:280px;">
            <select id="db-state-filter"
                    style="padding:0.4rem 0.75rem; border:1px solid var(--gray-300); border-radius:6px;
                           font-size:0.85rem;">
                <option value="">All States</option>
            </select>
            <select id="db-source-filter"
                    style="padding:0.4rem 0.75rem; border:1px solid var(--gray-300); border-radius:6px;
                           font-size:0.85rem;">
                <option value="">All Sources</option>
            </select>
            <label style="font-size:0.8rem; color:var(--gray-700); display:flex; align-items:center; gap:0.3rem;">
                <input type="checkbox" id="db-match-only"> Keyword matches only
            </label>
            <span id="db-count" style="font-size:0.8rem; color:var(--gray-500); margin-left:auto;"></span>
        </div>
        <div class="table-wrap" style="max-height: 600px; overflow-y: auto;">
            <table>
                <thead>
                    <tr>
                        <th>State</th>
                        <th>Title</th>
                        <th>Agency</th>
                        <th>Source</th>
                        <th>Open Date</th>
                        <th>Close Date</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody id="db-body"></tbody>
            </table>
        </div>
        <div style="margin-top:0.5rem; text-align:center;">
            <button id="db-load-more" class="chart-btn"
                    style="display:none;">Load more...</button>
        </div>
    </section>

</main>

<footer>
    Lookout Analytics &bull; Research RFP Scraper &bull; Updated daily at 12:01 AM CT
</footer>

<script>
// Data is inlined at build time -- works offline, no fetch() needed
const DATA = {json_blob};

document.addEventListener('DOMContentLoaded', () => {{
    const d = DATA;

    // --- Overview cards ---
    setText('last-updated', 'Last updated: ' + d.generated);
    setText('total-rfps', num(d.total_rfps));
    setText('keyword-matches', num(d.keyword_matches));
    setText('states-covered', d.states_covered);
    setText('sources-active', d.sources_active);
    setText('scrape-date', d.scrape_date);

    // --- Per-capita map ---
    renderMap(d.states);

    // --- Line chart ---
    renderLineChart(d.daily_counts || [], 'cumulative');

    // --- Full database ---
    initFullDatabase(d.full_database || []);

    // --- State bar chart + table ---
    const maxStateTotal = Math.max(...d.states.map(s => s.total));
    const stateBars = document.getElementById('state-bars');
    const stateBody = document.getElementById('state-table-body');

    d.states.forEach(s => {{
        const pct = (s.total / maxStateTotal * 100).toFixed(1);
        stateBars.innerHTML +=
            '<div class="bar-row">' +
            '  <span class="bar-label">' + esc(s.state) + '</span>' +
            '  <div class="bar-track">' +
            '    <div class="bar-fill" style="width:' + pct + '%">' +
            '      <span>' + num(s.total) + '</span>' +
            '    </div>' +
            '  </div>' +
            '</div>';

        const tr = document.createElement('tr');
        tr.innerHTML =
            '<td><strong>' + esc(s.state) + '</strong></td>' +
            '<td>' + num(s.total) + '</td>' +
            '<td>' + num(s.matches) + '</td>' +
            '<td>' + s.match_rate + '%</td>';
        stateBody.appendChild(tr);
    }});

    // --- Source table ---
    const srcBody = document.getElementById('source-table-body');
    d.sources.forEach(s => {{
        const tr = document.createElement('tr');
        let badge;
        if (s.total === 0) badge = '<span class="badge badge-red">No Data</span>';
        else if (s.matches > 0) badge = '<span class="badge badge-green">Active</span>';
        else badge = '<span class="badge badge-amber">No Matches</span>';
        tr.innerHTML =
            '<td>' + esc(s.source) + '</td>' +
            '<td>' + num(s.total) + '</td>' +
            '<td>' + num(s.matches) + '</td>' +
            '<td>' + badge + '</td>';
        srcBody.appendChild(tr);
    }});

    // --- TF-IDF bars ---
    if (d.top_tfidf && d.top_tfidf.length > 0) {{
        const maxScore = d.top_tfidf[0].score;
        const tfidfBars = document.getElementById('tfidf-bars');
        d.top_tfidf.forEach(t => {{
            const pct = (t.score / maxScore * 100).toFixed(1);
            tfidfBars.innerHTML +=
                '<div class="bar-row">' +
                '  <span class="bar-label wide">' + esc(t.term) + '</span>' +
                '  <div class="bar-track">' +
                '    <div class="bar-fill navy" style="width:' + pct + '%">' +
                '      <span>' + t.score.toFixed(4) + '</span>' +
                '    </div>' +
                '  </div>' +
                '</div>';
        }});
    }}

    // --- Keyword frequency bars ---
    if (d.keyword_frequency && d.keyword_frequency.length > 0) {{
        const maxKw = d.keyword_frequency[0].count;
        const kwBars = document.getElementById('keyword-freq-bars');
        d.keyword_frequency.forEach(k => {{
            const pct = (k.count / maxKw * 100).toFixed(1);
            kwBars.innerHTML +=
                '<div class="bar-row">' +
                '  <span class="bar-label wide">' + esc(k.keyword) + '</span>' +
                '  <div class="bar-track">' +
                '    <div class="bar-fill green" style="width:' + pct + '%">' +
                '      <span>' + k.count + '</span>' +
                '    </div>' +
                '  </div>' +
                '</div>';
        }});
    }}

    // --- Gap terms ---
    const gapDiv = document.getElementById('gap-terms');
    (d.gap_terms || []).forEach(g => {{
        gapDiv.innerHTML += '<span class="pill gap">' + esc(g.term) + '</span>';
    }});

    // --- RAKE phrases ---
    const rakeDiv = document.getElementById('rake-phrases');
    (d.rake_phrases || []).forEach(p => {{
        rakeDiv.innerHTML += '<span class="pill">' + esc(p) + '</span>';
    }});
}});

// --- Helpers ---
function setText(id, text) {{
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}}

function num(n) {{
    return (n || 0).toLocaleString();
}}

function esc(s) {{
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}}

// --- State map rendering ---
const STATE_NAMES = {{
    AL:'Alabama',AK:'Alaska',AZ:'Arizona',AR:'Arkansas',CA:'California',
    CO:'Colorado',CT:'Connecticut',DE:'Delaware',FL:'Florida',GA:'Georgia',
    HI:'Hawaii',ID:'Idaho',IL:'Illinois',IN:'Indiana',IA:'Iowa',
    KS:'Kansas',KY:'Kentucky',LA:'Louisiana',ME:'Maine',MD:'Maryland',
    MA:'Massachusetts',MI:'Michigan',MN:'Minnesota',MS:'Mississippi',
    MO:'Missouri',MT:'Montana',NE:'Nebraska',NV:'Nevada',NH:'New Hampshire',
    NJ:'New Jersey',NM:'New Mexico',NY:'New York',NC:'North Carolina',
    ND:'North Dakota',OH:'Ohio',OK:'Oklahoma',OR:'Oregon',PA:'Pennsylvania',
    RI:'Rhode Island',SC:'South Carolina',SD:'South Dakota',TN:'Tennessee',
    TX:'Texas',UT:'Utah',VT:'Vermont',VA:'Virginia',WA:'Washington',
    WV:'West Virginia',WI:'Wisconsin',WY:'Wyoming'
}};

function renderMap(states) {{
    // Build lookup: state code -> per_capita
    const pcMap = {{}};
    const totalMap = {{}};
    const matchMap = {{}};
    states.forEach(s => {{
        pcMap[s.state] = s.per_capita || 0;
        totalMap[s.state] = s.total || 0;
        matchMap[s.state] = s.matches || 0;
    }});

    // Get per-capita values (exclude Federal and zero)
    const pcValues = states
        .filter(s => s.state !== 'Federal' && (s.per_capita || 0) > 0)
        .map(s => s.per_capita);
    if (pcValues.length === 0) return;

    const minPC = Math.min(...pcValues);
    const maxPC = Math.max(...pcValues);

    // Color scale: light blue -> dark navy
    const colors = ['#eff6ff','#dbeafe','#bfdbfe','#93c5fd','#60a5fa','#3b82f6','#2563eb','#1d4ed8','#1e40af'];

    function getColor(val) {{
        if (!val || val === 0) return '#f3f4f6';
        // Log scale for better distribution
        const logMin = Math.log(minPC);
        const logMax = Math.log(maxPC);
        const logVal = Math.log(val);
        const ratio = (logVal - logMin) / (logMax - logMin || 1);
        const idx = Math.min(Math.floor(ratio * colors.length), colors.length - 1);
        return colors[idx];
    }}

    // Color each state path
    const svgEl = document.querySelector('.us-map');
    if (!svgEl) return;

    const paths = svgEl.querySelectorAll('path[id]');
    const tooltip = document.getElementById('map-tooltip');

    paths.forEach(path => {{
        const code = path.id;
        if (code.length !== 2) return;
        const pc = pcMap[code] || 0;
        path.style.fill = getColor(pc);
        path.style.cursor = 'pointer';
        path.style.stroke = '#fff';
        path.style.strokeWidth = '1';

        path.addEventListener('mouseenter', (e) => {{
            path.style.strokeWidth = '2.5';
            path.style.stroke = '#1b2a4a';
            const name = STATE_NAMES[code] || code;
            tooltip.innerHTML =
                '<strong>' + name + '</strong><br>' +
                'RFPs: ' + num(totalMap[code] || 0) + '<br>' +
                'Per capita: ' + (pc ? pc.toFixed(1) : '0') + '<br>' +
                'Matches: ' + num(matchMap[code] || 0);
            tooltip.style.display = 'block';
        }});

        path.addEventListener('mousemove', (e) => {{
            const wrap = document.getElementById('map-wrap');
            const rect = wrap.getBoundingClientRect();
            tooltip.style.left = (e.clientX - rect.left + 15) + 'px';
            tooltip.style.top = (e.clientY - rect.top - 10) + 'px';
        }});

        path.addEventListener('mouseleave', () => {{
            path.style.strokeWidth = '1';
            path.style.stroke = '#fff';
            tooltip.style.display = 'none';
        }});
    }});

    // Build legend
    const legendDiv = document.getElementById('map-legend');
    const legendMin = Math.floor(minPC);
    const legendMax = Math.ceil(maxPC);
    let legendHTML = '<span class="legend-label">' + legendMin + '</span>';
    colors.forEach(c => {{
        legendHTML += '<span class="legend-swatch" style="background:' + c + '"></span>';
    }});
    legendHTML += '<span class="legend-label">' + legendMax + ' per M pop</span>';
    legendDiv.innerHTML = legendHTML;
}}

// --- Line chart rendering (pure Canvas, no library) ---
function renderLineChart(daily, mode) {{
    const canvas = document.getElementById('line-chart');
    if (!canvas || daily.length === 0) {{
        if (canvas) {{
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#6b7280';
            ctx.font = '14px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Chart will populate as daily scrape data accumulates',
                         canvas.width / 2, canvas.height / 2);
        }}
        return;
    }}

    // Determine which data series to plot
    const isCumulative = (mode === 'cumulative');
    const rfpVals = daily.map(d => isCumulative ? d.cumulative_rfps : d.new_rfps);
    const matchVals = daily.map(d => isCumulative ? d.cumulative_matches : d.new_matches);
    const labels = daily.map(d => d.date);

    // Canvas setup with high-DPI support
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const W = rect.width;
    const H = rect.height;

    ctx.clearRect(0, 0, W, H);

    // Layout
    const pad = {{ top: 20, right: 20, bottom: 45, left: 60 }};
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    // Y range
    const allVals = [...rfpVals, ...matchVals];
    const yMax = Math.max(...allVals) * 1.1 || 10;
    const yMin = 0;

    // Grid lines
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;
    const gridLines = 5;
    ctx.font = '11px -apple-system, sans-serif';
    ctx.fillStyle = '#6b7280';
    ctx.textAlign = 'right';
    for (let i = 0; i <= gridLines; i++) {{
        const y = pad.top + plotH - (i / gridLines) * plotH;
        const val = Math.round((i / gridLines) * yMax);
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + plotW, y);
        ctx.stroke();
        ctx.fillText(val.toLocaleString(), pad.left - 8, y + 4);
    }}

    // X-axis labels
    ctx.textAlign = 'center';
    ctx.fillStyle = '#6b7280';
    const n = labels.length;
    const maxLabels = Math.min(n, 15);
    const step = Math.max(1, Math.floor(n / maxLabels));

    function xPos(i) {{
        if (n === 1) return pad.left + plotW / 2;
        return pad.left + (i / (n - 1)) * plotW;
    }}

    for (let i = 0; i < n; i += step) {{
        const x = xPos(i);
        // Show short date (MM/DD)
        const parts = labels[i].split('-');
        const shortDate = parts.length >= 3 ? parts[1] + '/' + parts[2] : labels[i];
        ctx.save();
        ctx.translate(x, pad.top + plotH + 12);
        ctx.rotate(-Math.PI / 6);
        ctx.fillText(shortDate, 0, 0);
        ctx.restore();
    }}

    // Draw line helper
    function drawLine(vals, color, fillAlpha) {{
        if (vals.length === 0) return;
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.lineJoin = 'round';

        for (let i = 0; i < vals.length; i++) {{
            const x = xPos(i);
            const y = pad.top + plotH - (vals[i] / yMax) * plotH;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }}
        ctx.stroke();

        // Fill area under line
        if (fillAlpha) {{
            ctx.lineTo(xPos(vals.length - 1), pad.top + plotH);
            ctx.lineTo(xPos(0), pad.top + plotH);
            ctx.closePath();
            ctx.fillStyle = color.replace(')', ',' + fillAlpha + ')').replace('rgb', 'rgba');
            ctx.fill();
        }}

        // Draw dots
        for (let i = 0; i < vals.length; i++) {{
            const x = xPos(i);
            const y = pad.top + plotH - (vals[i] / yMax) * plotH;
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }}
    }}

    // Draw the two lines
    drawLine(rfpVals, 'rgb(59,130,246)', '0.08');
    drawLine(matchVals, 'rgb(34,197,94)', '0.08');

    // Legend
    const legY = pad.top + 2;
    const legX = pad.left + 10;
    ctx.font = '12px -apple-system, sans-serif';

    ctx.fillStyle = 'rgb(59,130,246)';
    ctx.fillRect(legX, legY, 14, 10);
    ctx.fillStyle = '#374151';
    ctx.textAlign = 'left';
    ctx.fillText(isCumulative ? 'Total RFPs' : 'New RFPs', legX + 20, legY + 9);

    ctx.fillStyle = 'rgb(34,197,94)';
    ctx.fillRect(legX + 120, legY, 14, 10);
    ctx.fillStyle = '#374151';
    ctx.fillText(isCumulative ? 'Total Matches' : 'New Matches', legX + 140, legY + 9);
}}

// --- Chart toggle buttons ---
document.querySelectorAll('.chart-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
        document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderLineChart(DATA.daily_counts || [], btn.dataset.mode);
    }});
}});

// --- Full database with search, filters, and lazy loading ---
function initFullDatabase(allRows) {{
    const PAGE_SIZE = 100;
    let filtered = allRows;
    let shown = 0;

    const body = document.getElementById('db-body');
    const countEl = document.getElementById('db-count');
    const loadMoreBtn = document.getElementById('db-load-more');
    const searchInput = document.getElementById('db-search');
    const stateFilter = document.getElementById('db-state-filter');
    const sourceFilter = document.getElementById('db-source-filter');
    const matchOnly = document.getElementById('db-match-only');

    // Populate filter dropdowns
    const states = [...new Set(allRows.map(r => r.state))].filter(Boolean).sort();
    states.forEach(s => {{
        const opt = document.createElement('option');
        opt.value = s; opt.textContent = s;
        stateFilter.appendChild(opt);
    }});
    const sources = [...new Set(allRows.map(r => r.source))].filter(Boolean).sort();
    sources.forEach(s => {{
        const opt = document.createElement('option');
        opt.value = s; opt.textContent = s;
        sourceFilter.appendChild(opt);
    }});

    function applyFilters() {{
        const q = searchInput.value.toLowerCase().trim();
        const st = stateFilter.value;
        const src = sourceFilter.value;
        const mo = matchOnly.checked;

        filtered = allRows.filter(r => {{
            if (st && r.state !== st) return false;
            if (src && r.source !== src) return false;
            if (mo && !r.keyword_match) return false;
            if (q) {{
                const hay = (r.title + ' ' + r.agency + ' ' + r.state + ' ' + r.source).toLowerCase();
                if (!hay.includes(q)) return false;
            }}
            return true;
        }});

        shown = 0;
        body.innerHTML = '';
        renderPage();
    }}

    function renderPage() {{
        const end = Math.min(shown + PAGE_SIZE, filtered.length);
        for (let i = shown; i < end; i++) {{
            const r = filtered[i];
            const tr = document.createElement('tr');
            if (r.keyword_match) tr.style.background = '#f0fdf4';
            const titleCell = r.url
                ? '<a href="' + esc(r.url) + '" target="_blank" rel="noopener">' + esc(r.title) + '</a>'
                : esc(r.title);
            tr.innerHTML =
                '<td><strong>' + esc(r.state) + '</strong></td>' +
                '<td>' + titleCell + '</td>' +
                '<td>' + esc(r.agency) + '</td>' +
                '<td>' + esc(r.source) + '</td>' +
                '<td>' + esc(r.posted_date) + '</td>' +
                '<td>' + esc(r.close_date) + '</td>' +
                '<td>' + esc(r.amount) + '</td>';
            body.appendChild(tr);
        }}
        shown = end;
        countEl.textContent = 'Showing ' + num(shown) + ' of ' + num(filtered.length);
        loadMoreBtn.style.display = shown < filtered.length ? 'inline-block' : 'none';
    }}

    // Event listeners
    searchInput.addEventListener('input', applyFilters);
    stateFilter.addEventListener('change', applyFilters);
    sourceFilter.addEventListener('change', applyFilters);
    matchOnly.addEventListener('change', applyFilters);
    loadMoreBtn.addEventListener('click', renderPage);

    // Initial render
    renderPage();
}}
</script>

</body>
</html>'''


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_site() -> str:
    """Generate the local dashboard. Returns a log-friendly summary."""
    if not PARQUET_FILE.exists():
        return "Site generation skipped -- no Parquet data."

    summary = build_summary_data()
    render_html(summary)
    return (
        f"Site generated: {summary['total_rfps']} RFPs, "
        f"{summary['keyword_matches']} matches, "
        f"{summary['states_covered']} states"
    )


if __name__ == "__main__":
    result = generate_site()
    print(result)
