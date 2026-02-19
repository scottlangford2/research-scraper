"""
Inductive keyword extraction for RFPs.

Extracts salient terms from each RFP at scrape time using a lightweight
custom tokenizer with procurement-specific stop words.  Returns unigrams
and bigrams — no heavy NLP dependencies required at scrape time.
"""

import re
import string

# ---------------------------------------------------------------------------
# Stop words — English common + procurement boilerplate
# ---------------------------------------------------------------------------

_ENGLISH_STOP = frozenset(
    "a an the and or but in on at to for of is it its by from with as be was "
    "were been being have has had do does did will would shall should may might "
    "can could this that these those am are not no nor so if then than too very "
    "each every all any both few more most other some such only own same just "
    "about above after again against before below between during into out over "
    "through under until up also how what which who whom why where when there "
    "here their them they he she her his him we our us you your me my".split()
)

_PROCUREMENT_STOP = frozenset(
    "rfp rfq rfi ifb solicitation bid bids proposal proposals contract contracts "
    "amendment addendum addenda vendor vendors supplier suppliers bidder bidders "
    "services service provide providing provided provision procurement purchase "
    "purchasing request requests notice notices invitation invitations due date "
    "state county city town village district department dept division office "
    "agency bureau board commission authority university college school "
    "number num fiscal year month annual quarterly per new open closed awarded "
    "public issued release released issuing response responses submission "
    "submit submitted deadline period effective expiration renewal "
    "section item items page pages attachment exhibit appendix scope work "
    "required requirements requirement include includes including included "
    "shall must may general description specifications specification".split()
)

STOP_WORDS = _ENGLISH_STOP | _PROCUREMENT_STOP

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_MULTI_SPACE = re.compile(r"\s+")
_DIGITS_ONLY = re.compile(r"^\d+$")

MIN_WORD_LEN = 3
MAX_KEY_TERMS = 10


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into tokens, remove stop words."""
    text = _PUNCT_RE.sub(" ", text.lower())
    text = _MULTI_SPACE.sub(" ", text).strip()
    tokens = []
    for tok in text.split():
        if len(tok) < MIN_WORD_LEN:
            continue
        if _DIGITS_ONLY.match(tok):
            continue
        if tok in STOP_WORDS:
            continue
        tokens.append(tok)
    return tokens


def _bigrams(tokens: list[str]) -> list[str]:
    """Generate bigrams from token list."""
    return [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_key_terms(rfp: dict) -> list[str]:
    """Extract up to MAX_KEY_TERMS salient terms from an RFP.

    Combines the title, description, and agency fields.  Avoids
    double-counting when description == title (common in BidNet data).

    Returns a list of unique unigrams and bigrams, ordered by
    specificity (bigrams first, then unigrams).
    """
    title = rfp.get("title", "") or ""
    desc = rfp.get("description", "") or ""
    agency = rfp.get("agency", "") or ""

    # Avoid double-counting when description is just a copy of the title
    if desc.strip().lower() == title.strip().lower():
        desc = ""

    text = f"{title} {desc} {agency}".strip()
    if not text:
        return []

    tokens = _tokenize(text)
    if not tokens:
        return []

    # Count term frequency within this document
    freq: dict[str, int] = {}
    for tok in tokens:
        freq[tok] = freq.get(tok, 0) + 1

    # Generate bigrams and count them
    bi = _bigrams(tokens)
    bi_freq: dict[str, int] = {}
    for b in bi:
        bi_freq[b] = bi_freq.get(b, 0) + 1

    # Merge: bigrams get a 2x boost (multi-word phrases are more specific)
    scored: list[tuple[str, float]] = []
    for term, count in bi_freq.items():
        scored.append((term, count * 2.0))
    for term, count in freq.items():
        # Skip unigrams that are fully covered by a bigram
        if any(term in b for b in bi_freq):
            continue
        scored.append((term, count * 1.0))

    # Sort by score descending, then alphabetically for ties
    scored.sort(key=lambda x: (-x[1], x[0]))

    # Deduplicate and cap
    seen: set[str] = set()
    result: list[str] = []
    for term, _ in scored:
        if term not in seen:
            seen.add(term)
            result.append(term)
            if len(result) >= MAX_KEY_TERMS:
                break

    return result
