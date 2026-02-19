#!/usr/bin/env python3
"""
Corpus-level keyword discovery for the research scraper.

Can be run standalone (`python analyze_keywords.py`) for the full report,
or called from main.py via `run_analysis()` at the end of each scrape.

Methods:
  - TF-IDF (sklearn): unigram + bigram term importance across the corpus
  - RAKE (rake-nltk): multi-word keyphrase extraction on text-rich RFPs
  - Gap analysis: compare discovered terms against the deductive keyword list
  - New-term detection: diff against previous run to surface emerging terms

Output:
  - Full report: data/keyword_analysis.txt
  - Top terms snapshot: data/top_terms.json (for diff between runs)
  - Log summary each run

Usage (standalone):
    python analyze_keywords.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

# Add project root to path so we can import local modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PARQUET_FILE, DATA_DIR, log
from keywords import STOP_WORDS
from filters import KEYWORDS as DEDUCTIVE_KEYWORDS

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TOP_N_OVERALL = 50
TOP_N_PER_GROUP = 20
TOP_N_RAKE = 50
MIN_TEXT_LEN_RAKE = 80  # only apply RAKE to descriptions longer than this
REPORT_FILE = DATA_DIR / "keyword_analysis.txt"
TOP_TERMS_FILE = DATA_DIR / "top_terms.json"  # snapshot for diff detection

# Combined stop words for TF-IDF (English + procurement)
TFIDF_STOP = list(STOP_WORDS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_rfps() -> pd.DataFrame:
    """Load all RFPs from Parquet into a DataFrame."""
    if not PARQUET_FILE.exists():
        log.error(f"Parquet file not found: {PARQUET_FILE}")
        return pd.DataFrame()

    table = pq.read_table(PARQUET_FILE)
    df = table.to_pandas()
    log.info(f"Loaded {len(df)} RFPs from {PARQUET_FILE.name}")
    return df


def _build_text_column(df: pd.DataFrame) -> pd.Series:
    """Combine title + description, avoiding duplication when desc == title."""
    def _combine(row):
        title = str(row.get("title", "") or "")
        desc = str(row.get("description", "") or "")
        agency = str(row.get("agency", "") or "")

        # Avoid double-counting title copies
        if desc.strip().lower() == title.strip().lower():
            desc = ""

        return f"{title} {desc} {agency}".strip()

    return df.apply(_combine, axis=1)


def _load_previous_top_terms() -> dict:
    """Load the previous run's top-terms snapshot for diffing."""
    if TOP_TERMS_FILE.exists():
        try:
            with open(TOP_TERMS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_top_terms(terms: dict):
    """Save this run's top-terms snapshot."""
    with open(TOP_TERMS_FILE, "w") as f:
        json.dump(terms, f, indent=2)


# ---------------------------------------------------------------------------
# TF-IDF Analysis
# ---------------------------------------------------------------------------


def tfidf_analysis(df: pd.DataFrame, report_lines: list[str]) -> list[tuple[str, float]]:
    """Run TF-IDF analysis on the corpus. Returns top overall terms."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    report_lines.append("=" * 70)
    report_lines.append("TF-IDF ANALYSIS")
    report_lines.append("=" * 70)

    text_col = _build_text_column(df)

    # --- Overall corpus TF-IDF ---
    vectorizer = TfidfVectorizer(
        stop_words=TFIDF_STOP,
        ngram_range=(1, 2),
        max_features=5000,
        min_df=2,          # term must appear in at least 2 documents
        max_df=0.85,       # ignore terms in >85% of documents
        token_pattern=r"\b[a-zA-Z]{3,}\b",  # min 3 chars, alpha only
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(text_col)
    except ValueError as e:
        report_lines.append(f"\nTF-IDF failed: {e}")
        report_lines.append("(Likely too few documents or all terms filtered out)")
        return []

    feature_names = vectorizer.get_feature_names_out()

    # Mean TF-IDF score across all documents
    mean_scores = tfidf_matrix.mean(axis=0).A1
    top_indices = mean_scores.argsort()[::-1][:TOP_N_OVERALL]

    # Collect top terms for return value
    top_terms = [(feature_names[idx], float(mean_scores[idx])) for idx in top_indices]

    report_lines.append(f"\n--- Top {TOP_N_OVERALL} Terms (Overall Corpus) ---")
    report_lines.append(f"{'Rank':<6} {'Term':<40} {'TF-IDF Score':<12}")
    report_lines.append("-" * 58)
    for rank, (term, score) in enumerate(top_terms, 1):
        report_lines.append(f"{rank:<6} {term:<40} {score:.6f}")

    # --- By State ---
    report_lines.append(f"\n--- Top {TOP_N_PER_GROUP} Terms by State ---")
    for state, group in df.groupby("state"):
        if len(group) < 5:
            continue
        state_text = _build_text_column(group)
        try:
            state_matrix = vectorizer.transform(state_text)
            state_means = state_matrix.mean(axis=0).A1
            state_top = state_means.argsort()[::-1][:TOP_N_PER_GROUP]
            report_lines.append(f"\n  {state} ({len(group)} RFPs):")
            for idx in state_top:
                if state_means[idx] > 0:
                    report_lines.append(
                        f"    {feature_names[idx]:<40} {state_means[idx]:.6f}"
                    )
        except Exception:
            continue

    # --- By Source ---
    report_lines.append(f"\n--- Top {TOP_N_PER_GROUP} Terms by Source ---")
    for source, group in df.groupby("source"):
        if len(group) < 5:
            continue
        source_text = _build_text_column(group)
        try:
            source_matrix = vectorizer.transform(source_text)
            source_means = source_matrix.mean(axis=0).A1
            source_top = source_means.argsort()[::-1][:TOP_N_PER_GROUP]
            report_lines.append(f"\n  {source} ({len(group)} RFPs):")
            for idx in source_top:
                if source_means[idx] > 0:
                    report_lines.append(
                        f"    {feature_names[idx]:<40} {source_means[idx]:.6f}"
                    )
        except Exception:
            continue

    # --- Matched vs Unmatched comparison ---
    if "keyword_match" in df.columns:
        report_lines.append("\n--- Matched vs. Unmatched Comparison ---")

        matched_df = df[df["keyword_match"] == True]  # noqa: E712
        unmatched_df = df[df["keyword_match"] == False]  # noqa: E712

        if len(matched_df) >= 5 and len(unmatched_df) >= 5:
            matched_text = _build_text_column(matched_df)
            unmatched_text = _build_text_column(unmatched_df)

            try:
                matched_matrix = vectorizer.transform(matched_text)
                unmatched_matrix = vectorizer.transform(unmatched_text)

                matched_means = matched_matrix.mean(axis=0).A1
                unmatched_means = unmatched_matrix.mean(axis=0).A1

                # Terms enriched in matched RFPs
                diff = matched_means - unmatched_means
                enriched = diff.argsort()[::-1][:20]
                report_lines.append(
                    f"\n  Terms enriched in MATCHED RFPs ({len(matched_df)} RFPs):"
                )
                for idx in enriched:
                    if diff[idx] > 0:
                        report_lines.append(
                            f"    {feature_names[idx]:<40} +{diff[idx]:.6f}"
                        )

                # Terms enriched in unmatched RFPs
                depleted = diff.argsort()[:20]
                report_lines.append(
                    f"\n  Terms enriched in UNMATCHED RFPs ({len(unmatched_df)} RFPs):"
                )
                for idx in depleted:
                    if diff[idx] < 0:
                        report_lines.append(
                            f"    {feature_names[idx]:<40} {diff[idx]:.6f}"
                        )
            except Exception as e:
                report_lines.append(f"  Comparison failed: {e}")

    return top_terms


# ---------------------------------------------------------------------------
# RAKE Analysis
# ---------------------------------------------------------------------------


def rake_analysis(df: pd.DataFrame, report_lines: list[str]) -> list[tuple[float, str]]:
    """Run RAKE keyphrase extraction on text-rich RFPs. Returns top phrases."""
    try:
        from rake_nltk import Rake
    except ImportError:
        report_lines.append("\n" + "=" * 70)
        report_lines.append("RAKE ANALYSIS — SKIPPED (rake-nltk not installed)")
        report_lines.append("Install with: pip install rake-nltk")
        return []

    report_lines.append("\n" + "=" * 70)
    report_lines.append("RAKE ANALYSIS (text-rich RFPs only)")
    report_lines.append("=" * 70)

    text_col = _build_text_column(df)
    long_text = text_col[text_col.str.len() >= MIN_TEXT_LEN_RAKE]

    report_lines.append(
        f"\nRFPs with description >= {MIN_TEXT_LEN_RAKE} chars: "
        f"{len(long_text)} of {len(df)} total"
    )

    if len(long_text) < 5:
        report_lines.append("Too few text-rich RFPs for meaningful RAKE analysis.")
        return []

    rake = Rake(
        stopwords=list(STOP_WORDS),
        min_length=2,       # minimum 2 words per phrase
        max_length=4,       # maximum 4 words per phrase
    )

    # Combine all text-rich descriptions into one extraction
    combined = " . ".join(long_text.tolist())
    rake.extract_keywords_from_text(combined)
    ranked = rake.get_ranked_phrases_with_scores()

    # Deduplicate similar phrases
    seen_phrases: set[str] = set()
    unique_ranked: list[tuple[float, str]] = []
    for score, phrase in ranked:
        normalized = " ".join(sorted(phrase.lower().split()))
        if normalized not in seen_phrases:
            seen_phrases.add(normalized)
            unique_ranked.append((score, phrase))

    report_lines.append(f"\n--- Top {TOP_N_RAKE} RAKE Keyphrases ---")
    report_lines.append(f"{'Rank':<6} {'Phrase':<50} {'Score':<10}")
    report_lines.append("-" * 66)

    for rank, (score, phrase) in enumerate(unique_ranked[:TOP_N_RAKE], 1):
        report_lines.append(f"{rank:<6} {phrase:<50} {score:.2f}")

    return unique_ranked[:TOP_N_RAKE]


# ---------------------------------------------------------------------------
# Gap Analysis
# ---------------------------------------------------------------------------


def gap_analysis(df: pd.DataFrame, report_lines: list[str]) -> list[tuple[str, float]]:
    """Compare discovered terms against the deductive keyword list. Returns gaps."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    report_lines.append("\n" + "=" * 70)
    report_lines.append("GAP ANALYSIS: Discovered Terms vs. Deductive Keywords")
    report_lines.append("=" * 70)

    text_col = _build_text_column(df)

    vectorizer = TfidfVectorizer(
        stop_words=TFIDF_STOP,
        ngram_range=(1, 2),
        max_features=5000,
        min_df=2,
        max_df=0.85,
        token_pattern=r"\b[a-zA-Z]{3,}\b",
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(text_col)
    except ValueError:
        report_lines.append("TF-IDF failed — cannot perform gap analysis.")
        return []

    feature_names = vectorizer.get_feature_names_out()
    mean_scores = tfidf_matrix.mean(axis=0).A1

    # Normalize deductive keywords for comparison
    deductive_lower = {kw.lower() for kw in DEDUCTIVE_KEYWORDS}

    # Find high-scoring TF-IDF terms NOT in the deductive list
    scored_terms = sorted(
        zip(feature_names, mean_scores),
        key=lambda x: -x[1],
    )

    report_lines.append(
        f"\nDeductive keyword list: {len(deductive_lower)} terms"
    )
    report_lines.append(
        f"TF-IDF vocabulary: {len(feature_names)} terms"
    )

    gaps: list[tuple[str, float]] = []
    for term, score in scored_terms:
        if score < 0.001:
            continue
        # Check if term is already covered by any deductive keyword
        covered = any(term in kw or kw in term for kw in deductive_lower)
        if not covered:
            gaps.append((term, float(score)))

    report_lines.append(
        f"\n--- Top 30 High-Scoring Terms NOT in Deductive Keywords ---"
    )
    report_lines.append(
        "These are candidates for adding to the KEYWORDS list in filters.py"
    )
    report_lines.append(f"\n{'Rank':<6} {'Term':<40} {'TF-IDF Score':<12}")
    report_lines.append("-" * 58)

    for rank, (term, score) in enumerate(gaps[:30], 1):
        report_lines.append(f"{rank:<6} {term:<40} {score:.6f}")

    # Also check which deductive keywords appear frequently
    report_lines.append(f"\n--- Deductive Keywords Found in TF-IDF Vocabulary ---")
    found = []
    not_found = []
    for kw in sorted(deductive_lower):
        if kw in set(feature_names):
            idx = list(feature_names).index(kw)
            found.append((kw, mean_scores[idx]))
        else:
            not_found.append(kw)

    report_lines.append(f"\n  Found in corpus: {len(found)} of {len(deductive_lower)}")
    if found:
        found.sort(key=lambda x: -x[1])
        report_lines.append(f"\n  Top 20 most active deductive keywords:")
        for kw, score in found[:20]:
            report_lines.append(f"    {kw:<40} {score:.6f}")

    if not_found:
        report_lines.append(
            f"\n  Not found in corpus ({len(not_found)} keywords — "
            "may need more data or different sources):"
        )
        for kw in not_found[:30]:
            report_lines.append(f"    {kw}")
        if len(not_found) > 30:
            report_lines.append(f"    ... and {len(not_found) - 30} more")

    return gaps[:30]


# ---------------------------------------------------------------------------
# New-term detection (diff between runs)
# ---------------------------------------------------------------------------


def detect_new_terms(
    current_top: list[tuple[str, float]],
    current_gaps: list[tuple[str, float]],
    current_rake: list[tuple[float, str]],
    report_lines: list[str],
) -> dict:
    """Compare current top terms against previous run, log new/rising terms.

    Returns the snapshot dict to save for next run's comparison.
    """
    previous = _load_previous_top_terms()

    # Build current snapshot
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "top_tfidf": {term: score for term, score in current_top[:TOP_N_OVERALL]},
        "gap_terms": {term: score for term, score in current_gaps[:30]},
        "rake_phrases": [phrase for _, phrase in current_rake[:TOP_N_RAKE]],
    }

    report_lines.append("\n" + "=" * 70)
    report_lines.append("NEW TERM DETECTION (vs. previous run)")
    report_lines.append("=" * 70)

    prev_tfidf = previous.get("top_tfidf", {})
    prev_gaps = set(previous.get("gap_terms", {}).keys())
    prev_rake = set(previous.get("rake_phrases", []))
    prev_ts = previous.get("timestamp", "never")

    report_lines.append(f"\n  Previous run: {prev_ts}")
    report_lines.append(f"  Current run:  {snapshot['timestamp']}")

    if not prev_tfidf:
        report_lines.append("\n  No previous run data — this is the baseline.")
        _save_top_terms(snapshot)
        return snapshot

    # --- New TF-IDF terms (in current top 50 but not in previous top 50) ---
    current_tfidf_set = set(snapshot["top_tfidf"].keys())
    prev_tfidf_set = set(prev_tfidf.keys())

    new_terms = current_tfidf_set - prev_tfidf_set
    dropped_terms = prev_tfidf_set - current_tfidf_set

    if new_terms:
        report_lines.append(f"\n  NEW in top {TOP_N_OVERALL} TF-IDF terms ({len(new_terms)}):")
        for term in sorted(new_terms):
            report_lines.append(f"    + {term:<40} {snapshot['top_tfidf'][term]:.6f}")
    else:
        report_lines.append(f"\n  No new terms in top {TOP_N_OVERALL} TF-IDF.")

    if dropped_terms:
        report_lines.append(f"\n  DROPPED from top {TOP_N_OVERALL} ({len(dropped_terms)}):")
        for term in sorted(dropped_terms):
            report_lines.append(f"    - {term}")

    # --- Rising terms (score increased by >10%) ---
    rising = []
    for term, score in snapshot["top_tfidf"].items():
        if term in prev_tfidf:
            prev_score = prev_tfidf[term]
            if prev_score > 0 and (score - prev_score) / prev_score > 0.10:
                rising.append((term, prev_score, score))

    if rising:
        rising.sort(key=lambda x: (x[2] - x[1]) / x[1], reverse=True)
        report_lines.append(f"\n  RISING terms (>10% score increase, {len(rising)}):")
        for term, old, new in rising[:15]:
            pct = (new - old) / old * 100
            report_lines.append(
                f"    {term:<40} {old:.6f} -> {new:.6f}  (+{pct:.0f}%)"
            )

    # --- New gap candidates ---
    current_gap_set = set(snapshot["gap_terms"].keys())
    new_gaps = current_gap_set - prev_gaps
    if new_gaps:
        report_lines.append(f"\n  NEW gap candidates ({len(new_gaps)}):")
        for term in sorted(new_gaps):
            report_lines.append(
                f"    + {term:<40} {snapshot['gap_terms'][term]:.6f}"
            )

    # --- New RAKE phrases ---
    current_rake_set = set(snapshot["rake_phrases"])
    new_rake = current_rake_set - prev_rake
    if new_rake:
        report_lines.append(f"\n  NEW RAKE phrases ({len(new_rake)}):")
        for phrase in sorted(new_rake):
            report_lines.append(f"    + {phrase}")

    _save_top_terms(snapshot)
    return snapshot


# ---------------------------------------------------------------------------
# Public API (called from main.py)
# ---------------------------------------------------------------------------


def run_analysis() -> str:
    """Run the full keyword analysis and return a log-friendly summary.

    Called automatically at the end of each scrape run.
    Saves the full report to data/keyword_analysis.txt and
    returns a short summary string for the scrape log.
    """
    df = _load_rfps()
    if df.empty:
        return "Keyword analysis skipped — no data."

    report_lines: list[str] = []
    report_lines.append("=" * 70)
    report_lines.append("RESEARCH SCRAPER — KEYWORD ANALYSIS REPORT")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Total RFPs: {len(df)}")
    report_lines.append(f"States: {df['state'].nunique()}")
    report_lines.append(f"Sources: {df['source'].nunique()}")

    if "keyword_match" in df.columns:
        matched = int(df["keyword_match"].sum())
        report_lines.append(
            f"Keyword matches: {matched} ({matched/len(df)*100:.1f}%)"
        )

    report_lines.append("=" * 70)

    # Run analyses
    top_terms = tfidf_analysis(df, report_lines)
    rake_phrases = rake_analysis(df, report_lines)
    gap_terms = gap_analysis(df, report_lines)

    # Detect new/rising terms vs. previous run
    snapshot = detect_new_terms(top_terms, gap_terms, rake_phrases, report_lines)

    # Save full report
    report = "\n".join(report_lines)
    REPORT_FILE.write_text(report, encoding="utf-8")

    # Build short summary for the log
    prev = _load_previous_top_terms()
    prev_tfidf = set(prev.get("top_tfidf", {}).keys()) if prev.get("timestamp") != snapshot.get("timestamp") else set()
    current_tfidf = set(snapshot.get("top_tfidf", {}).keys())
    new_count = len(current_tfidf - prev_tfidf) if prev_tfidf else 0

    summary_parts = [
        f"Keyword analysis: {len(df)} RFPs",
        f"top TF-IDF: {top_terms[0][0] if top_terms else 'n/a'}",
        f"gap candidates: {len(gap_terms)}",
    ]
    if new_count:
        summary_parts.append(f"new terms: {new_count}")

    summary = " | ".join(summary_parts)
    return summary


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main():
    """Standalone CLI entrypoint — prints full report."""
    log.info("Starting corpus-level keyword analysis...")
    summary = run_analysis()
    log.info(summary)
    log.info(f"Full report saved to {REPORT_FILE}")


if __name__ == "__main__":
    main()
