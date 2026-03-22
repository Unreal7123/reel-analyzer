"""
NLP Detection Layer — rule-based + emoji/spam signal analysis.

Now uses spam comment patterns and emoji frequencies as additional
signals alongside the text-based rule patterns.
"""

import re
import logging
from collections import Counter
from models import ScrapedData, NLPResult, SpamAnalysis, TopComment, TopEmoji

logger = logging.getLogger(__name__)

# ── Resource vocabulary ────────────────────────────────────────────────────────
_TRIGGER_VERBS = r"(?:comment|type|reply|dm|message|send|write|say|drop|leave|tag)"
_RESOURCE_WORDS = (
    r"(?:link|url|pdf|doc|ebook|guide|freebie|resource|template|checklist"
    r"|file|download|course|cheatsheet|cheat\s*sheet|blueprint|swipe|toolkit"
    r"|video|training|workshop|webinar|masterclass|script|prompt|notion"
    r"|free(?:bie)?|gift|bonus|access|giveaway)"
)
_QUOTE = r"""[\"'\u2018\u2019\u201c\u201d\u275b-\u275e]"""

# ── Rule patterns ──────────────────────────────────────────────────────────────
RULE_PATTERNS: list[tuple[str, re.Pattern, int]] = [
    ("comment_trigger_keyword",
     re.compile(rf"{_TRIGGER_VERBS}\s+{_QUOTE}?{_RESOURCE_WORDS}{_QUOTE}?", re.I), 35),

    ("dm_trigger",
     re.compile(rf"\b(?:dm|direct\s*message|message\s*me|send\s*me)\b.{{0,40}}\b{_RESOURCE_WORDS}\b", re.I|re.S), 30),

    ("bio_link_reference",
     re.compile(r"\b(?:link|free|pdf|resource)\b.{0,30}\b(?:in\s+(?:my\s+)?bio|bio\s+link)\b", re.I|re.S), 20),

    ("get_free_resource",
     re.compile(rf"\b(?:get|grab|download|access|claim|receive)\b.{{0,30}}\b(?:free\s+)?{_RESOURCE_WORDS}\b", re.I|re.S), 15),

    ("want_comment_below",
     re.compile(rf"\bwant.{{0,40}}{_RESOURCE_WORDS}.{{0,30}}comment\b", re.I|re.S), 25),

    ("manychat_pattern",
     re.compile(r"\b(?:manychat|many\s*chat|auto\s*reply|autorespond|keyword\s*reply)\b", re.I), 40),

    ("save_post_cta",
     re.compile(r"\bsave\s+(?:this\s+)?(?:post|reel|video)\b", re.I), 10),

    ("reply_to_get",
     re.compile(rf"\breply\b.{{0,30}}\b(?:to\s+)?(?:get|receive|download)\b.{{0,30}}\b{_RESOURCE_WORDS}\b", re.I|re.S), 30),

    ("keyword_in_quotes",
     re.compile(rf"(?:keyword|word|magic\s+word)\s*[:\-]?\s*{_QUOTE}.{{1,20}}{_QUOTE}", re.I), 35),
]

# ── Automation emojis (commonly used in CTA comments) ─────────────────────────
# These emojis appearing frequently in comments = strong automation signal
AUTOMATION_EMOJIS = {
    "🔗": 25, "📄": 20, "📩": 25, "📥": 25, "💌": 20, "👇": 15,
    "⬇️": 15, "✅": 10, "🎁": 20, "📖": 15, "📚": 15, "🔥": 5,
    "💯": 5,  "👀": 10, "💬": 20, "🤖": 30, "⚡": 10, "🚀": 5,
    "📲": 20, "📤": 20, "🆓": 25, "🎯": 10, "💡": 10,
}

_KEYWORD_EXTRACT = re.compile(
    rf"(?:{_QUOTE})({_RESOURCE_WORDS})(?:{_QUOTE})|"
    rf"\b({_RESOURCE_WORDS})\b",
    re.I,
)


def _extract_trigger_keywords(text: str) -> list[str]:
    kws: set[str] = set()
    for m in _KEYWORD_EXTRACT.finditer(text):
        kw = (m.group(1) or m.group(2) or "").strip().lower()
        if kw:
            kws.add(kw)
    return sorted(kws)


def _build_spam_analysis(metadata: dict) -> SpamAnalysis:
    """Convert raw spam analysis dict from scraper into SpamAnalysis model."""
    raw = metadata.get("spam_analysis", {})
    if not raw:
        return SpamAnalysis()
    return SpamAnalysis(
        top_comments=[TopComment(**c) for c in raw.get("top_comments", [])],
        top_emojis=[TopEmoji(**e) for e in raw.get("top_emojis", [])],
        spam_score=raw.get("spam_score", 0),
        total_comments=raw.get("total_comments", 0),
    )


def _score_spam_signals(spam: SpamAnalysis) -> tuple[int, list[str]]:
    """
    Score automation likelihood from spam analysis.
    Returns (bonus_score, human_readable_signals).
    """
    score = 0
    signals: list[str] = []

    # High comment repetition = automation trigger
    if spam.spam_score >= 60:
        score += 25
        signals.append(f"High comment repetition ({spam.spam_score}% spam rate)")
    elif spam.spam_score >= 30:
        score += 12
        signals.append(f"Moderate comment repetition ({spam.spam_score}% spam rate)")

    # Top comments matching automation keywords
    for tc in spam.top_comments[:5]:
        text_lower = tc.text.lower()
        for keyword in ["link", "pdf", "guide", "ebook", "send", "dm", "yes", "interested", "more info"]:
            if keyword in text_lower and tc.count >= 3:
                score += 15
                signals.append(f"'{tc.text[:30]}' repeated {tc.count}× in comments")
                break

    # Automation emojis in top emojis
    for te in spam.top_emojis:
        if te.emoji in AUTOMATION_EMOJIS and te.count >= 3:
            bonus = min(AUTOMATION_EMOJIS[te.emoji], 20)
            score += bonus
            signals.append(f"Automation emoji {te.emoji} used {te.count}× in comments")

    return min(score, 50), signals   # cap spam bonus at 50


# ── Optional spaCy ────────────────────────────────────────────────────────────
_nlp = None
try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
    logger.info("spaCy loaded: en_core_web_sm")
except Exception:
    logger.info("spaCy not available — rule-based only")


def _spacy_boost(text: str) -> int:
    if not _nlp:
        return 0
    doc = _nlp(text[:4000])
    bonus = 0
    for token in doc:
        if token.pos_ == "VERB" and token.dep_ == "ROOT":
            for child in token.children:
                if child.lemma_.lower() in {"link","pdf","guide","ebook","resource","file","template"}:
                    bonus += 5
    return min(bonus, 15)


# ── Main detector ──────────────────────────────────────────────────────────────

def detect_automation(data: ScrapedData) -> NLPResult:
    corpus = data.raw_text_corpus or (data.caption + "\n" + "\n".join(data.comments))
    raw_score = 0
    matched_patterns: list[str] = []

    # Rule-based pass
    for label, pattern, base_score in RULE_PATTERNS:
        if pattern.search(corpus):
            matched_patterns.append(label)
            raw_score += base_score
            logger.debug(f"Pattern '{label}' matched (+{base_score})")

    # Keyword density bonus
    density = len(re.findall(rf"\b{_RESOURCE_WORDS}\b", corpus, re.I))
    raw_score += min(density * 3, 15)

    # Spam signal bonus (new)
    spam = _build_spam_analysis(data.post_metadata)
    spam_bonus, spam_signals = _score_spam_signals(spam)
    raw_score += spam_bonus

    # spaCy bonus
    raw_score += _spacy_boost(corpus)

    confidence_score = min(raw_score, 100)
    automation_detected = confidence_score >= 20

    trigger_keywords = _extract_trigger_keywords(corpus) if automation_detected else []

    return NLPResult(
        automation_detected=automation_detected,
        trigger_keywords=trigger_keywords,
        confidence_score=confidence_score,
        matched_patterns=matched_patterns,
        spam_signals=spam_signals,
        nlp_model_used="rule_based + spaCy" if _nlp else "rule_based",
    )