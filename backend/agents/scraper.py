"""
Scraper — multi-strategy public Instagram Reel data extractor.
Uses httpx only (no Playwright). Extracts embedded JSON from page HTML.
"""

import re
import json
import asyncio
import logging
from collections import Counter
from typing import Optional
import httpx
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import ScrapedData

logger = logging.getLogger(__name__)

EMOJI_RE   = re.compile(
    "[\U0001F300-\U0001F9FF\U0001FA00-\U0001FAFF"
    "\U00002600-\U000027BF\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF\U00002702-\U000027B0\U0000FE0F]+",
    flags=re.UNICODE,
)
HASHTAG_RE = re.compile(r"#[\w\u00C0-\u024F\u0400-\u04FF]+", re.UNICODE)
URL_RE     = re.compile(r"https?://[^\s\"'<>)\]]+", re.I)

# Multiple user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def _make_headers(ua_index: int = 0) -> dict:
    return {
        "User-Agent": USER_AGENTS[ua_index % len(USER_AGENTS)],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
    }


# ── HTML parsing strategies ───────────────────────────────────────────────────

def _extract_jsonld(html: str) -> dict:
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I
    ):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") in (
                        "VideoObject", "ImageObject", "SocialMediaPosting"
                    ):
                        return item
            elif isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def _parse_jsonld(data: dict) -> str:
    for key in ("caption", "description", "articleBody", "name"):
        v = data.get(key, "")
        if v and len(v) > 3:
            return v.strip()
    return ""


def _extract_shared_data(html: str) -> dict:
    m = re.search(r'window\._sharedData\s*=\s*(\{.+?\});\s*</script>', html, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return {}


def _parse_shared_data(sd: dict) -> tuple[str, list[str]]:
    caption = ""
    comments: list[str] = []
    try:
        media = (
            sd.get("entry_data", {})
            .get("PostPage", [{}])[0]
            .get("graphql", {})
            .get("shortcode_media", {})
        )
        edges = media.get("edge_media_to_caption", {}).get("edges", [])
        if edges:
            caption = edges[0].get("node", {}).get("text", "")
        for edge in media.get("edge_media_to_parent_comment", {}).get("edges", []):
            node = edge.get("node", {})
            t = node.get("text", "").strip()
            if t:
                comments.append(t)
            for re_ in node.get("edge_threaded_comments", {}).get("edges", []):
                rt = re_.get("node", {}).get("text", "").strip()
                if rt:
                    comments.append(rt)
    except Exception as e:
        logger.debug(f"shared_data parse: {e}")
    return caption, comments


def _extract_relay_data(html: str) -> tuple[str, list[str]]:
    """Extract from __RelayPageProps__ or similar script blobs."""
    caption = ""
    comments: list[str] = []
    patterns = [
        r'"caption"\s*:\s*\{\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}',
        r'"edge_media_to_caption".*?"text":"((?:[^"\\]|\\.)*)"',
        r'"text"\s*:\s*"((?:[^"\\]|\\.){20,})"',  # any long text field
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            try:
                candidate = m.group(1).encode().decode('unicode_escape')
                if len(candidate) > 10:
                    caption = candidate
                    break
            except Exception:
                caption = m.group(1)
                break

    # Extract comment texts
    comment_matches = re.findall(
        r'"edge_media_to_comment".*?"edges"\s*:\s*(\[.*?\])',
        html, re.S
    )
    for block in comment_matches[:1]:
        try:
            edges = json.loads(block)
            for edge in edges:
                t = edge.get("node", {}).get("text", "").strip()
                if t:
                    comments.append(t)
        except Exception:
            pass

    return caption, comments


def _extract_meta(html: str, prop: str) -> str:
    for pat in [
        rf'<meta[^>]+property=["\']og:{prop}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:{prop}["\']',
        rf'<meta[^>]+name=["\']{prop}["\'][^>]+content=["\'](.*?)["\']',
    ]:
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1).strip()
    return ""


def _extract_external_urls(html: str) -> list[str]:
    urls = []
    for m in URL_RE.finditer(html):
        u = m.group()
        if any(skip in u for skip in ["instagram.com", "cdninstagram", "fbcdn", "facebook.com", "whatsapp"]):
            continue
        if any(ext in u.lower() for ext in [".pdf", ".doc", "linktr.ee", "linktree", "bit.ly", "beacons", "bio.link"]):
            urls.append(u)
    return list(set(urls))[:20]


# ── Spam analysis ─────────────────────────────────────────────────────────────

def _analyze_spam(raw_comments: list[str]) -> dict:
    if not raw_comments:
        return {"top_comments": [], "top_emojis": [], "spam_score": 0, "total_comments": 0}

    comment_counter: Counter = Counter()
    emoji_counter: Counter = Counter()

    for c in raw_comments:
        key = re.sub(r"\s+", " ", c.lower().strip())
        comment_counter[key] += 1
        for emoji in EMOJI_RE.findall(c):
            for ch in emoji:
                emoji_counter[ch] += 1

    top_comments = [
        {"text": t, "count": n}
        for t, n in comment_counter.most_common(10) if n >= 2
    ]
    top_emojis = [
        {"emoji": e, "count": n}
        for e, n in emoji_counter.most_common(10)
    ]
    total = len(raw_comments)
    repeated = sum(n for n in comment_counter.values() if n > 1)
    return {
        "top_comments": top_comments,
        "top_emojis": top_emojis,
        "spam_score": round((repeated / total) * 100) if total else 0,
        "total_comments": total,
    }


# ── Main scraper ──────────────────────────────────────────────────────────────

async def scrape_reel(url: str) -> ScrapedData:
    caption = ""
    comments: list[str] = []
    html = ""

    # Try fetching with multiple strategies
    for attempt in range(3):
        try:
            headers = _make_headers(attempt)
            # Add cookies on retry attempts
            cookies = {}
            if attempt >= 1:
                cookies = {"ig_did": "anonymous", "csrftoken": "missing"}

            async with httpx.AsyncClient(
                headers=headers,
                cookies=cookies,
                follow_redirects=True,
                timeout=25.0,
            ) as client:
                resp = await client.get(url)
                logger.info(f"Attempt {attempt+1}: status={resp.status_code} size={len(resp.text):,}")
                if resp.status_code == 200 and len(resp.text) > 5000:
                    # Check we didn't get a login redirect
                    if "login" in resp.url.path.lower() or "accounts/login" in str(resp.url):
                        logger.warning("Got redirected to login page")
                        await asyncio.sleep(2)
                        continue
                    html = resp.text
                    break
                await asyncio.sleep(1.5)
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed: {e}")
            await asyncio.sleep(2)

    if not html:
        logger.error("All fetch attempts failed")
        return ScrapedData(
            post_metadata={"url": url, "spam_analysis": {}, "inline_urls": [], "error": "Could not fetch page"},
            raw_text_corpus="",
        )

    # Strategy 1: JSON-LD
    jsonld = _extract_jsonld(html)
    if jsonld:
        caption = _parse_jsonld(jsonld)
        logger.info(f"JSON-LD caption: {caption[:60]!r}")

    # Strategy 2: _sharedData
    sd = _extract_shared_data(html)
    if sd:
        cap2, coms2 = _parse_shared_data(sd)
        if not caption and cap2:
            caption = cap2
        if not comments and coms2:
            comments = coms2
        logger.info(f"sharedData: cap={bool(cap2)} comments={len(coms2)}")

    # Strategy 3: Relay data blobs
    if not caption or not comments:
        cap3, coms3 = _extract_relay_data(html)
        if not caption and cap3:
            caption = cap3
        if not comments and coms3:
            comments = coms3
        logger.info(f"Relay: cap={bool(cap3)} comments={len(coms3)}")

    # Strategy 4: og:description meta tag
    if not caption:
        caption = _extract_meta(html, "description") or _extract_meta(html, "title")
        logger.info(f"Meta caption: {caption[:60]!r}")

    # External URLs
    inline_urls = _extract_external_urls(html)
    logger.info(f"External URLs: {inline_urls[:3]}")

    # Spam analysis
    spam = _analyze_spam(comments)
    logger.info(f"Caption:{len(caption)}ch | Comments:{len(comments)} | Spam:{spam['spam_score']}%")

    # Deduplicate comments
    seen: set[str] = set()
    unique_comments: list[str] = []
    for c in comments:
        k = c.lower().strip()
        if k and k not in seen:
            seen.add(k)
            unique_comments.append(c)

    full_text = caption + " " + " ".join(unique_comments)
    hashtags = list(set(HASHTAG_RE.findall(full_text)))
    corpus = "\n".join(filter(None, [caption] + unique_comments))

    return ScrapedData(
        caption=caption,
        hashtags=hashtags,
        comments=unique_comments,
        bio_link=inline_urls[0] if inline_urls else None,
        post_metadata={
            "url": url,
            "spam_analysis": spam,
            "inline_urls": inline_urls,
        },
        raw_text_corpus=corpus,
    )
