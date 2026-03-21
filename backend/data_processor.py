"""
Data Processing Layer

Cleans and normalises text extracted by the scraper before NLP analysis.
Removes emojis, normalizes unicode, deduplicates, and rebuilds a clean corpus.
"""

import re
import unicodedata
from models import ScrapedData

# ─── Emoji + noise patterns ────────────────────────────────────────────────────

# Match broad Unicode emoji ranges
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002700-\U000027BF"  # dingbats
    "\U0000200D"             # zero-width joiner
    "\U00002640-\U00002642"
    "\U00002600-\U00002B55"
    "\U000023CF"
    "\U000023E9"
    "\U000023F3"
    "\U0001F004"
    "\U0001F0CF"
    "\U0001F170-\U0001F171"
    "\U0001F17E-\U0001F17F"
    "\U0001F18E"
    "\U0001F191-\U0001F19A"
    "\U0001F201-\U0001F202"
    "\U0001F21A"
    "\U0001F22F"
    "\U0001F232-\U0001F23A"
    "\U0001F250-\U0001F251"
    "]+",
    flags=re.UNICODE,
)

# Invisible / zero-width characters Instagram injects
_INVISIBLE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad]")

# Repeated punctuation
_REPEATED_PUNCT = re.compile(r"([!?.]{3,})")

# Spam patterns (repeated characters, "AAAAAAA")
_REPEATED_CHARS = re.compile(r"(.)\1{4,}")

# Simple spam heuristic: if >70% of chars are the same char
def _is_spam(text: str) -> bool:
    if len(text) < 5:
        return False
    most_common = max(set(text.lower()), key=text.lower().count)
    return text.lower().count(most_common) / len(text) > 0.7


# ─── Normalization ─────────────────────────────────────────────────────────────

def _normalize_keywords(text: str) -> str:
    """
    Normalize casing/spacing for known trigger keywords so rule matching is
    more reliable. E.g. "LINK" → "link", "e book" → "ebook".
    """
    t = text.lower()
    t = re.sub(r"\be[\s\-]book\b", "ebook", t)
    t = re.sub(r"\bcheat[\s\-]sheet\b", "cheatsheet", t)
    t = re.sub(r"\bpd\s*f\b", "pdf", t)
    return t


def clean_text(text: str) -> str:
    """Full pipeline for a single string."""
    # 1. Strip invisible chars
    text = _INVISIBLE.sub("", text)
    # 2. Normalize unicode (NFKC handles full-width chars, ligatures, etc.)
    text = unicodedata.normalize("NFKC", text)
    # 3. Remove emojis
    text = _EMOJI_PATTERN.sub(" ", text)
    # 4. Collapse repeated punctuation
    text = _REPEATED_PUNCT.sub(r"\1", text)
    # 5. Collapse repeated characters
    text = _REPEATED_CHARS.sub(r"\1\1", text)
    # 6. Normalize keyword forms
    text = _normalize_keywords(text)
    # 7. Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─── Process ScrapedData ───────────────────────────────────────────────────────

def process_scraped_data(data: ScrapedData) -> ScrapedData:
    """
    Return a new ScrapedData with all text fields cleaned and normalised.
    Removes duplicate / spam comments and rebuilds the raw_text_corpus.
    """
    cleaned_caption = clean_text(data.caption)

    # Clean, deduplicate, filter spam comments
    seen: set[str] = set()
    cleaned_comments: list[str] = []
    for comment in data.comments:
        c = clean_text(comment)
        c_lower = c.lower()
        if not c or c_lower in seen or _is_spam(c):
            continue
        seen.add(c_lower)
        cleaned_comments.append(c)

    cleaned_hashtags = [h.lower() for h in data.hashtags]

    # Rebuild corpus
    corpus = "\n".join([cleaned_caption] + cleaned_comments)

    return ScrapedData(
        caption=cleaned_caption,
        hashtags=cleaned_hashtags,
        comments=cleaned_comments,
        bio_link=data.bio_link,
        post_metadata=data.post_metadata,
        raw_text_corpus=corpus,
    )
