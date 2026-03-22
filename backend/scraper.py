"""
Scraper Layer — multi-strategy Instagram public data extractor.

Strategy order (fastest/most reliable first):
  1. httpx raw HTML → JSON-LD embedded in <script> tags  (no browser needed)
  2. httpx raw HTML → window.__additionalDataLoaded JSON blob
  3. httpx raw HTML → meta tags (og:description, og:title)
  4. Playwright stealth fallback (last resort)

Instagram embeds full post data as JSON-LD and in script tags on every
public page — this works without a browser and without authentication.

Legal: Only reads publicly rendered content. No login, no auth bypass.
"""

import re
import json
import asyncio
import logging
from collections import Counter
from typing import Optional

import httpx
from playwright.async_api import async_playwright

from models import ScrapedData

logger = logging.getLogger(__name__)

# ── Patterns ──────────────────────────────────────────────────────────────────
EMOJI_RE   = re.compile(
    "[\U0001F300-\U0001F9FF\U0001FA00-\U0001FAFF"
    "\U00002600-\U000027BF\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF\U00002702-\U000027B0\U0000FE0F]+",
    flags=re.UNICODE,
)
HASHTAG_RE = re.compile(r"#[\w\u00C0-\u024F\u0400-\u04FF]+", re.UNICODE)
URL_RE     = re.compile(r"https?://[^\s\"'<>)\]]+", re.I)

# ── HTTP headers that look like a real browser ────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}


# ── Strategy 1: JSON-LD extraction ────────────────────────────────────────────

def _extract_jsonld(html: str) -> dict:
    """Extract Instagram's JSON-LD structured data from page HTML."""
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.S | re.I,
    )
    for match in pattern.finditer(html):
        try:
            data = json.loads(match.group(1))
            # Can be a list or dict
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


def _extract_shared_data(html: str) -> dict:
    """Extract window._sharedData JSON blob."""
    m = re.search(r'window\._sharedData\s*=\s*(\{.+?\});</script>', html, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return {}


def _extract_additional_data(html: str) -> dict:
    """Extract window.__additionalDataLoaded JSON blob."""
    m = re.search(r'__additionalDataLoaded\s*\(\s*["\'][^"\']+["\'],\s*(\{.+?\})\s*\)', html, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return {}


def _extract_meta(html: str, prop: str) -> str:
    m = re.search(
        rf'<meta[^>]+(?:property|name)=["\']og:{prop}["\'][^>]+content=["\'](.*?)["\']',
        html, re.I,
    )
    if not m:
        m = re.search(
            rf'<meta[^>]+content=["\'](.*?)["\'][^>]+(?:property|name)=["\']og:{prop}["\']',
            html, re.I,
        )
    return m.group(1).strip() if m else ""


# ── Parse caption + comments from various JSON shapes ─────────────────────────

def _parse_jsonld_caption(data: dict) -> str:
    for key in ("caption", "description", "articleBody", "name"):
        val = data.get(key, "")
        if val and len(val) > 3:
            return val.strip()
    return ""


def _parse_shared_data_caption(sd: dict) -> tuple[str, list[str]]:
    caption  = ""
    comments: list[str] = []
    try:
        # Navigate into sharedData structure
        page_data = (
            sd.get("entry_data", {})
            .get("PostPage", [{}])[0]
            .get("graphql", {})
            .get("shortcode_media", {})
        )
        if not page_data:
            return caption, comments

        # Caption
        edges = (
            page_data.get("edge_media_to_caption", {})
            .get("edges", [])
        )
        if edges:
            caption = edges[0].get("node", {}).get("text", "")

        # Comments
        comment_edges = (
            page_data.get("edge_media_to_parent_comment", {})
            .get("edges", [])
        )
        for edge in comment_edges:
            node = edge.get("node", {})
            text = node.get("text", "").strip()
            if text:
                comments.append(text)
            # Replies
            reply_edges = node.get("edge_threaded_comments", {}).get("edges", [])
            for re_ in reply_edges:
                rt = re_.get("node", {}).get("text", "").strip()
                if rt:
                    comments.append(rt)
    except Exception as e:
        logger.debug(f"shared_data parse error: {e}")
    return caption, comments


# ── Comment spam analysis ────────────────────────────────────────────────────

def _analyze_spam(raw_comments: list[str]) -> dict:
    if not raw_comments:
        return {"top_comments": [], "top_emojis": [], "spam_score": 0, "total_comments": 0}

    comment_counter: Counter = Counter()
    emoji_counter:   Counter = Counter()

    for c in raw_comments:
        key = re.sub(r"\s+", " ", c.lower().strip())
        comment_counter[key] += 1
        for emoji in EMOJI_RE.findall(c):
            for ch in emoji:
                emoji_counter[ch] += 1

    top_comments = [
        {"text": t, "count": n}
        for t, n in comment_counter.most_common(10)
        if n >= 2
    ]
    top_emojis = [
        {"emoji": e, "count": n}
        for e, n in emoji_counter.most_common(10)
    ]
    total    = len(raw_comments)
    repeated = sum(n for n in comment_counter.values() if n > 1)
    spam_score = round((repeated / total) * 100) if total else 0

    return {
        "top_comments":   top_comments,
        "top_emojis":     top_emojis,
        "spam_score":     spam_score,
        "total_comments": total,
    }


# ── Strategy 2: Playwright stealth (fallback) ─────────────────────────────────

async def _playwright_fallback(url: str) -> tuple[str, list[str]]:
    """Last-resort Playwright scrape with maximum stealth settings."""
    caption  = ""
    comments: list[str] = []

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-setuid-sandbox",
                    "--single-process",
                    "--disable-infobars",
                    "--window-size=1280,900",
                ],
            )
            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                extra_http_headers={k: v for k, v in HEADERS.items() if k != "User-Agent"},
            )
            # Mask webdriver flag
            await context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )

            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=35_000)
            await asyncio.sleep(3)

            html = await page.content()
            caption = _extract_meta(html, "description") or _extract_meta(html, "title")

            # Try to get comments from rendered DOM
            for sel in [
                "ul._a9ym li div._a9zs span._aacl",
                "ul._a9ym li span._aacl",
                "article ul li span",
            ]:
                els = await page.query_selector_all(sel)
                for el in els:
                    t = (await el.inner_text()).strip()
                    if t:
                        comments.append(t)
                if comments:
                    break

            await browser.close()
    except Exception as e:
        logger.warning(f"Playwright fallback failed: {e}")

    return caption, comments


# ── Main entry point ──────────────────────────────────────────────────────────

async def scrape_reel(url: str) -> ScrapedData:
    """
    Multi-strategy scraper. Tries fast httpx HTML parsing first,
    falls back to Playwright only if needed.
    """
    caption  = ""
    comments: list[str] = []
    bio_link: Optional[str] = None
    inline_urls: list[str] = []

    # ── Fetch raw HTML with httpx ─────────────────────────────────────────────
    html = ""
    try:
        async with httpx.AsyncClient(
            headers=HEADERS,
            follow_redirects=True,
            timeout=20.0,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                html = resp.text
                logger.info(f"httpx fetch OK — {len(html):,} chars")
            else:
                logger.warning(f"httpx status {resp.status_code}")
    except Exception as e:
        logger.warning(f"httpx fetch failed: {e}")

    # ── Strategy A: JSON-LD ───────────────────────────────────────────────────
    if html:
        jsonld = _extract_jsonld(html)
        if jsonld:
            caption = _parse_jsonld_caption(jsonld)
            logger.info(f"JSON-LD caption: {caption[:80]!r}")

    # ── Strategy B: _sharedData ───────────────────────────────────────────────
    if html and (not caption or not comments):
        sd = _extract_shared_data(html)
        if sd:
            cap2, coms2 = _parse_shared_data_caption(sd)
            if not caption and cap2:
                caption = cap2
            if not comments:
                comments = coms2
            logger.info(f"sharedData comments: {len(comments)}")

    # ── Strategy C: meta tags ─────────────────────────────────────────────────
    if html and not caption:
        caption = _extract_meta(html, "description") or _extract_meta(html, "title")
        logger.info(f"meta caption: {caption[:80]!r}")

    # ── Strategy D: inline URLs from HTML ────────────────────────────────────
    if html:
        # Look for URLs in the raw HTML that aren't instagram assets
        for m in URL_RE.finditer(html):
            u = m.group()
            if any(skip in u for skip in ["instagram.com", "cdninstagram", "fbcdn", "facebook"]):
                continue
            if any(ext in u for ext in [".pdf", ".doc", "linktr.ee", "linktree", "bit.ly"]):
                inline_urls.append(u)
        inline_urls = list(set(inline_urls))[:20]
        logger.info(f"Inline external URLs found: {len(inline_urls)}")

    # ── Strategy E: Playwright fallback if we got nothing ────────────────────
    if not caption and not comments:
        logger.info("All httpx strategies failed — trying Playwright fallback")
        caption, comments = await _playwright_fallback(url)

    # ── Spam analysis ─────────────────────────────────────────────────────────
    spam = _analyze_spam(comments)
    logger.info(
        f"Final — caption:{len(caption)}ch | comments:{len(comments)} | "
        f"spam:{spam['spam_score']}% | urls:{len(inline_urls)}"
    )

    # ── Deduplicate comments ──────────────────────────────────────────────────
    seen: set[str] = set()
    unique_comments: list[str] = []
    for c in comments:
        k = c.lower().strip()
        if k and k not in seen:
            seen.add(k)
            unique_comments.append(c)

    # ── Hashtags ──────────────────────────────────────────────────────────────
    full_text = caption + " " + " ".join(unique_comments)
    hashtags  = list(set(HASHTAG_RE.findall(full_text)))

    corpus = "\n".join(filter(None, [caption] + unique_comments))

    return ScrapedData(
        caption=caption,
        hashtags=hashtags,
        comments=unique_comments,
        bio_link=bio_link,
        post_metadata={
            "url":           url,
            "spam_analysis": spam,
            "inline_urls":   inline_urls,
        },
        raw_text_corpus=corpus,
    )