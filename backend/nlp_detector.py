"""
NLP Detection Layer — Core Logic

Detects Instagram automation patterns (e.g. "comment 'link' to get PDF").
Two-tier approach:
  1. Rule-based keyword matching (always runs, fast, deterministic)
  2. Optional spaCy / sentence-transformer model (if installed)

The confidence score weights:
  - Pattern match count
  - Keyword density in corpus
  - Proximity of trigger verb + keyword in same sentence
"""

import re
import logging
from typing import Optional
from models import ScrapedData, NLPResult

logger = logging.getLogger(__name__)

# ─── Rule Patterns ────────────────────────────────────────────────────────────
# Each entry: (human label, compiled regex, base_score)
# Regex uses IGNORECASE + word-boundary-aware groups

_TRIGGER_VERBS = r"(?:comment|type|reply|dm|message|send|write|say|drop|leave)"
_RESOURCE_WORDS = (
    r"(?:link|url|pdf|doc|ebook|guide|freebie|resource|template|checklist"
    r"|file|download|course|cheatsheet|cheat\s*sheet|blueprint|swipe|toolkit"
    r"|video|training|workshop|webinar|masterclass|script|prompt|notion)"
)
_QUOTE_CHARS = r"""[\"'\u2018\u2019\u201c\u201d\u275b\u275c\u275d\u275e]"""

RULE_PATTERNS: list[tuple[str, re.Pattern, int]] = [
    # "comment 'link' below" / "type 'link' to get"
    (
        "comment_trigger_keyword",
        re.compile(
            rf"{_TRIGGER_VERBS}\s+{_QUOTE_CHARS}?{_RESOURCE_WORDS}{_QUOTE_CHARS}?",
            re.IGNORECASE,
        ),
        35,
    ),
    # "DM me 'guide'" / "DM for pdf"
    (
        "dm_trigger",
        re.compile(
            rf"\b(?:dm|direct\s*message|message\s*me|send\s*me)\b.*?\b{_RESOURCE_WORDS}\b",
            re.IGNORECASE | re.DOTALL,
        ),
        30,
    ),
    # "free pdf in bio" / "link in bio"
    (
        "bio_link_reference",
        re.compile(
            r"\b(?:link|free|pdf|resource)\b.{0,30}\b(?:in\s+bio|in\s+my\s+bio|bio\s+link)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        20,
    ),
    # "get the free ebook" / "grab the guide"
    (
        "get_free_resource",
        re.compile(
            rf"\b(?:get|grab|download|access|claim|receive)\b.{{0,30}}\b(?:free\s+)?{_RESOURCE_WORDS}\b",
            re.IGNORECASE | re.DOTALL,
        ),
        15,
    ),
    # "save this post" (soft signal)
    (
        "save_post_cta",
        re.compile(r"\bsave\s+(?:this\s+)?(?:post|reel|video)\b", re.IGNORECASE),
        10,
    ),
    # "want the X? just comment below"
    (
        "want_comment_below",
        re.compile(
            rf"\bwant.{{0,40}}{_RESOURCE_WORDS}.{{0,30}}comment\b",
            re.IGNORECASE | re.DOTALL,
        ),
        25,
    ),
    # ManyChat / Manychat keyword — strong signal
    (
        "manychat_pattern",
        re.compile(r"\b(?:manychat|many\s*chat|auto\s*reply|autorespond)\b", re.IGNORECASE),
        40,
    ),
]

# ─── Keyword extraction ────────────────────────────────────────────────────────

_KEYWORD_EXTRACT = re.compile(
    rf"(?:{_QUOTE_CHARS})({_RESOURCE_WORDS})(?:{_QUOTE_CHARS})|"
    rf"\b({_RESOURCE_WORDS})\b",
    re.IGNORECASE,
)


def _extract_trigger_keywords(text: str) -> list[str]:
    keywords: set[str] = set()
    for m in _KEYWORD_EXTRACT.finditer(text):
        kw = (m.group(1) or m.group(2) or "").strip().lower()
        if kw:
            keywords.add(kw)
    return sorted(keywords)


# ─── spaCy (optional) ─────────────────────────────────────────────────────────

_SPACY_AVAILABLE = False
_nlp = None

try:
    import spacy  # noqa: F401
    _nlp = spacy.load("en_core_web_sm")
    _SPACY_AVAILABLE = True
    logger.info("spaCy model loaded: en_core_web_sm")
except Exception:
    logger.info("spaCy not available — using rule-based detection only")


def _spacy_boost(text: str) -> int:
    """
    Use spaCy NER / dependency parsing for a confidence boost.
    Returns an integer bonus score (0–20).
    """
    if not _SPACY_AVAILABLE or not _nlp:
        return 0
    doc = _nlp(text[:5000])  # cap to avoid memory issues
    bonus = 0
    for token in doc:
        # Imperative verbs near resource nouns → stronger signal
        if token.pos_ == "VERB" and token.dep_ == "ROOT":
            for child in token.children:
                if child.lemma_.lower() in {
                    "link", "pdf", "guide", "ebook", "resource", "file"
                }:
                    bonus += 5
    return min(bonus, 20)


# ─── Main detector ─────────────────────────────────────────────────────────────

def detect_automation(data: ScrapedData) -> NLPResult:
    """
    Run the full detection pipeline on ScrapedData.
    Returns NLPResult with confidence_score, trigger_keywords, etc.
    """
    corpus = data.raw_text_corpus or (
        data.caption + "\n" + "\n".join(data.comments)
    )
    corpus_lower = corpus.lower()

    matched_patterns: list[str] = []
    raw_score = 0

    # ── Rule-based pass ───────────────────────────────────────────────────
    for label, pattern, base_score in RULE_PATTERNS:
        if pattern.search(corpus):
            matched_patterns.append(label)
            raw_score += base_score
            logger.debug(f"Pattern matched: {label} (+{base_score})")

    # ── Keyword density bonus ─────────────────────────────────────────────
    resource_hits = len(
        re.findall(rf"\b{_RESOURCE_WORDS}\b", corpus_lower, re.IGNORECASE)
    )
    density_bonus = min(resource_hits * 3, 15)
    raw_score += density_bonus

    # ── spaCy bonus ───────────────────────────────────────────────────────
    spacy_bonus = _spacy_boost(corpus)
    raw_score += spacy_bonus

    # ── Clamp to 0–100 ────────────────────────────────────────────────────
    confidence_score = min(raw_score, 100)

    # ── Decision threshold ────────────────────────────────────────────────
    automation_detected = confidence_score >= 20

    trigger_keywords = _extract_trigger_keywords(corpus) if automation_detected else []

    model_used = "rule_based + spaCy" if _SPACY_AVAILABLE else "rule_based"

    return NLPResult(
        automation_detected=automation_detected,
        trigger_keywords=trigger_keywords,
        confidence_score=confidence_score,
        matched_patterns=matched_patterns,
        nlp_model_used=model_used,
    )
