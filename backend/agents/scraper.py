"""
ReelScan Scraper  —  Three-tier data extraction engine
======================================================

Tier 1  Playwright (Chromium, headless)
        • Injects session cookies from env vars when available
        • Intercepts Instagram's internal XHR/GraphQL API responses
        • Falls back to DOM parsing (OG meta, JSON-LD) within the same tier
        • Best data quality; requires ~2–4 s per request

Tier 2  curl-cffi  (Chrome TLS fingerprint, no browser overhead)
        • Mimics a real Chrome TLS handshake (JA3/JA4)
        • Sends correct x-ig-app-id, Sec-Ch-Ua, Origin, Referer headers
        • Extracts OG description and JSON-LD title tags
        • Fast (~0.5 s); partial data

Tier 3  Instagram oEmbed API  (official, minimal, zero auth when no token)
        • Hits the public /oembed endpoint (no token) for title + author
        • If env var FACEBOOK_ACCESS_TOKEN is set, uses Graph API for richer data
        • Always succeeds on public reels; returns partial data

Each tier is tried in sequence; the first to return a non-empty caption
short-circuits the chain.  All tiers share the same ScrapedData return type
so the rest of the pipeline is completely unaffected.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from collections import Counter
from typing import Any
from urllib.parse import urlparse, quote

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import ScrapedData
from agents.session_manager import get_instagram_cookies, get_facebook_token

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Instagram's fixed web-app ID (public, non-secret — present in every browser request)
IG_APP_ID = "936619743392459"

# Standard headers every real Chrome browser sends to Instagram
_BASE_HEADERS: dict[str, str] = {
    "Accept":                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language":       "en-US,en;q=0.9",
    "Accept-Encoding":       "gzip, deflate, br",
    "Cache-Control":         "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":        "document",
    "Sec-Fetch-Mode":        "navigate",
    "Sec-Fetch-Site":        "none",
    "Sec-Fetch-User":        "?1",
    "Sec-Ch-Ua":             '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile":      "?0",
    "Sec-Ch-Ua-Platform":    '"Windows"',
    "Origin":                "https://www.instagram.com",
    "Referer":               "https://www.instagram.com/",
    "x-ig-app-id":           IG_APP_ID,
}

# XHR headers for JSON API calls (added on top of _BASE_HEADERS)
_XHR_HEADERS: dict[str, str] = {
    "Accept":         "application/json",
    "x-requested-with": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

_HASHTAG_RE = re.compile(r"#[\w\u00C0-\u024F\u0400-\u04FF]+", re.UNICODE)
_URL_RE     = re.compile(r"https?://[^\s\"'<>)\]]+", re.I)

# Domains we skip when collecting external links from page HTML
_SKIP_DOMAINS = frozenset(
    ["instagram.com", "cdninstagram.com", "fbcdn.net", "facebook.com", "whatsapp.com"]
)

# Domains / path segments that suggest a resource link
_RESOURCE_HINTS = frozenset(
    [".pdf", ".doc", ".docx", ".zip", "linktr.ee", "linktree", "bit.ly",
     "beacons.ai", "bio.link", "flowpage.com", "taplink.cc", "solo.to"]
)

# ── Shortcode helpers ─────────────────────────────────────────────────────────

_B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def _shortcode_from_url(url: str) -> str | None:
    """Extract Instagram shortcode from a reel / post URL."""
    m = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]{6,})", url)
    return m.group(1) if m else None


def _shortcode_to_media_id(shortcode: str) -> int:
    """Decode Instagram base-64 shortcode → numeric media ID."""
    n = 0
    for ch in shortcode:
        if ch not in _B64_ALPHABET:
            break
        n = n * 64 + _B64_ALPHABET.index(ch)
    return n


# ── Shared HTML parsers ───────────────────────────────────────────────────────

def _parse_og_tags(html: str) -> dict[str, str]:
    """Extract Open Graph meta-tag values from raw HTML."""
    result: dict[str, str] = {}
    for prop in ("description", "title", "url", "type"):
        patterns = [
            rf'<meta[^>]+property=["\']og:{prop}["\'][^>]+content=["\'](.*?)["\']',
            rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:{prop}["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.I | re.S)
            if m:
                result[prop] = m.group(1).strip()
                break
    return result


def _parse_jsonld(html: str) -> str:
    """Return best caption string found in any JSON-LD <script> block."""
    for m in re.finditer(
        r'<script[^>]+type=["\'"]application/ld\+json["\'"][^>]*>(.*?)</script>',
        html, re.S | re.I
    ):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                for key in ("caption", "description", "articleBody", "name"):
                    v = item.get(key, "")
                    if v and len(v) > 5:
                        return v.strip()
        except Exception:
            continue
    return ""


def _extract_external_urls(html: str) -> list[str]:
    """Collect non-Instagram URLs from raw HTML that look like resource links."""
    seen: set[str] = set()
    results: list[str] = []
    for m in _URL_RE.finditer(html):
        u = m.group().rstrip(".,;)")
        parsed = urlparse(u)
        host = parsed.netloc.lower().lstrip("www.")
        if any(skip in host for skip in _SKIP_DOMAINS):
            continue
        if any(hint in u.lower() for hint in _RESOURCE_HINTS):
            if u not in seen:
                seen.add(u)
                results.append(u)
    return results[:20]


def _extract_media_info_from_api(data: dict) -> tuple[str, list[str]]:
    """
    Parse caption and comment texts from Instagram's internal /api/v1/media/info/
    JSON response.
    """
    caption = ""
    comments: list[str] = []
    try:
        items = data.get("items", [])
        if not items:
            return caption, comments
        item = items[0]

        # Caption
        cap_node = item.get("caption")
        if isinstance(cap_node, dict):
            caption = cap_node.get("text", "")
        elif isinstance(cap_node, str):
            caption = cap_node

        # Comments (preview list, limited to 20)
        for edge in item.get("preview_comments", []) or []:
            t = (edge.get("text") or "").strip()
            if t:
                comments.append(t)
    except Exception as exc:
        logger.debug("_extract_media_info_from_api error: %s", exc)
    return caption, comments


def _extract_caption_from_graphql(data: dict) -> str:
    """Recursively hunt for a caption/text field in a GraphQL response blob."""
    def _hunt(obj: Any, depth: int = 0) -> str:
        if depth > 8:
            return ""
        if isinstance(obj, dict):
            for key in ("caption", "description", "text", "articleBody"):
                v = obj.get(key, "")
                if isinstance(v, str) and len(v) > 10:
                    return v.strip()
                if isinstance(v, dict):
                    t = (v.get("text") or v.get("caption") or "").strip()
                    if len(t) > 10:
                        return t
            for v in obj.values():
                found = _hunt(v, depth + 1)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj[:5]:
                found = _hunt(item, depth + 1)
                if found:
                    return found
        return ""

    return _hunt(data)


def _analyze_spam(raw_comments: list[str]) -> dict:
    if not raw_comments:
        return {"top_comments": [], "top_emojis": [], "spam_score": 0, "total_comments": 0}
    emoji_re = re.compile(
        "[\U0001F300-\U0001F9FF\U0001FA00-\U0001FAFF"
        "\U00002600-\U000027BF\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF\U00002702-\U000027B0\U0000FE0F]+",
        flags=re.UNICODE,
    )
    comment_counter: Counter = Counter()
    emoji_counter:   Counter = Counter()
    for c in raw_comments:
        comment_counter[re.sub(r"\s+", " ", c.lower().strip())] += 1
        for emoji in emoji_re.findall(c):
            for ch in emoji:
                emoji_counter[ch] += 1

    total    = len(raw_comments)
    repeated = sum(n for n in comment_counter.values() if n > 1)
    return {
        "top_comments":   [{"text": t, "count": n} for t, n in comment_counter.most_common(10) if n >= 2],
        "top_emojis":     [{"emoji": e, "count": n} for e, n in emoji_counter.most_common(10)],
        "spam_score":     round((repeated / total) * 100) if total else 0,
        "total_comments": total,
    }


def _build_scraped_data(
    url: str,
    caption: str,
    comments: list[str],
    inline_urls: list[str],
    tier: str,
) -> ScrapedData:
    full_text = caption + " " + " ".join(comments)
    hashtags  = list(set(_HASHTAG_RE.findall(full_text)))
    spam      = _analyze_spam(comments)
    bio_link  = inline_urls[0] if inline_urls else None

    # Deduplicate comments
    seen: set[str] = set()
    unique_comments: list[str] = []
    for c in comments:
        k = c.lower().strip()
        if k and k not in seen:
            seen.add(k)
            unique_comments.append(c)

    corpus = "\n".join(filter(None, [caption] + unique_comments))
    return ScrapedData(
        caption=caption,
        hashtags=hashtags,
        comments=unique_comments,
        bio_link=bio_link,
        post_metadata={
            "url":          url,
            "scrape_tier":  tier,
            "spam_analysis": spam,
            "inline_urls":  inline_urls,
        },
        raw_text_corpus=corpus,
    )


# ── Tier 1: Playwright ────────────────────────────────────────────────────────

async def _tier1_playwright(url: str) -> ScrapedData | None:
    """
    Playwright Chromium scraper with XHR interception.

    Strategy A: intercept /api/v1/media/{id}/info/ XHR → richest data
    Strategy B: intercept /graphql/query/ XHR → fallback
    Strategy C: DOM parsing after networkidle → OG tags + JSON-LD

    Cookies are injected from env vars when present (see session_manager.py).
    """
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.warning("Playwright not installed — skipping Tier 1")
        return None

    cookies   = get_instagram_cookies()
    has_auth  = bool(cookies)
    caption   = ""
    comments: list[str] = []
    intercepted_xhr: list[dict] = []      # raw JSON from intercepted XHR calls

    logger.info("Tier 1 [Playwright] starting (auth=%s)", has_auth)

    async def _handle_response(response) -> None:
        """Collect relevant API responses for post-processing."""
        resp_url = response.url
        try:
            # Instagram media info endpoint
            if "/api/v1/media/" in resp_url and "/info/" in resp_url:
                data = await response.json()
                intercepted_xhr.append({"type": "media_info", "data": data})
                logger.debug("Intercepted media/info (size=%d)", len(str(data)))

            # Instagram GraphQL endpoint
            elif "graphql/query" in resp_url:
                data = await response.json()
                intercepted_xhr.append({"type": "graphql", "data": data})
                logger.debug("Intercepted graphql/query")

            # NextJS page data (newer IG web)
            elif resp_url.endswith("/__data.json") or "page-data.json" in resp_url:
                data = await response.json()
                intercepted_xhr.append({"type": "page_data", "data": data})

        except Exception as exc:
            logger.debug("XHR intercept parse error (%s): %s", resp_url[:80], exc)

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--disable-gpu",
                ],
            )

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language":   "en-US,en;q=0.9",
                    "x-ig-app-id":       IG_APP_ID,
                    "Sec-Ch-Ua":         '"Chromium";v="124", "Google Chrome";v="124"',
                    "Sec-Ch-Ua-Mobile":  "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                },
            )

            # Inject session cookies if available
            if cookies:
                await context.add_cookies(cookies)
                logger.info("Injected %d session cookies", len(cookies))

            page = await context.new_page()

            # Hide webdriver fingerprint
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)

            # Register XHR interceptor before navigation
            page.on("response", lambda r: asyncio.ensure_future(_handle_response(r)))

            # Navigate
            try:
                await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=35_000,
                )
            except PWTimeout:
                logger.warning("Playwright: networkidle timeout — proceeding with partial load")
                # Continue anyway — partial interception may still have data

            final_url = page.url
            logger.info("Playwright landed on: %s", final_url)

            # ── Login-wall detection ──────────────────────────────────────────
            if "accounts/login" in final_url or "challenge" in final_url:
                logger.warning("Playwright: login wall detected (cookies required)")
                await browser.close()
                return None  # signal to try next tier

            # ── Wait for Instagram's XHR calls to complete ────────────────────
            await asyncio.sleep(2.0)

            # ── Parse intercepted XHR data (Strategy A + B) ───────────────────
            for item in intercepted_xhr:
                if caption:
                    break
                t    = item["type"]
                data = item["data"]
                if t == "media_info":
                    cap, coms = _extract_media_info_from_api(data)
                    if cap:
                        caption  = cap
                        comments = coms
                        logger.info("Playwright: caption from media/info XHR (%d chars)", len(cap))
                elif t in ("graphql", "page_data"):
                    cap = _extract_caption_from_graphql(data)
                    if cap:
                        caption = cap
                        logger.info("Playwright: caption from %s XHR (%d chars)", t, len(cap))

            # ── DOM fallback (Strategy C) ──────────────────────────────────────
            if not caption:
                html = await page.content()

                # OG description
                og = _parse_og_tags(html)
                caption = og.get("description", "") or og.get("title", "")
                if caption:
                    logger.info("Playwright: caption from OG tags (%d chars)", len(caption))

                # JSON-LD
                if not caption:
                    caption = _parse_jsonld(html)
                    if caption:
                        logger.info("Playwright: caption from JSON-LD (%d chars)", len(caption))

                # Try visible article / caption element text
                if not caption:
                    try:
                        locators = [
                            'meta[property="og:description"]',
                            'h1',
                            '[data-testid="post-comment-root"]',
                        ]
                        for loc in locators:
                            elem = page.locator(loc).first
                            if await elem.count() > 0:
                                text = (await elem.text_content() or "").strip()
                                if len(text) > 10:
                                    caption = text
                                    break
                    except Exception as exc:
                        logger.debug("Playwright DOM locator error: %s", exc)

                inline_urls = _extract_external_urls(html)
            else:
                # If we got caption from XHR, still check DOM for external links
                try:
                    html = await page.content()
                    inline_urls = _extract_external_urls(html)
                except Exception:
                    inline_urls = []

            await browser.close()

            if not caption:
                logger.info("Playwright: no caption extracted")
                return None  # try next tier

            logger.info(
                "Playwright: success | caption=%d chars | comments=%d | urls=%d",
                len(caption), len(comments), len(inline_urls),
            )
            return _build_scraped_data(url, caption, comments, inline_urls, "playwright")

    except Exception as exc:
        logger.error("Tier 1 [Playwright] failed: %s", exc, exc_info=True)
        return None


# ── Tier 2: curl-cffi ─────────────────────────────────────────────────────────

async def _tier2_curlffi(url: str) -> ScrapedData | None:
    """
    curl-cffi scraper using Chrome's TLS fingerprint.

    Sends proper browser headers including x-ig-app-id, Sec-Ch-Ua, Origin,
    Referer.  Returns partial data from OG tags / JSON-LD — no XHR interception.
    """
    try:
        from curl_cffi.requests import AsyncSession as CurlSession
    except ImportError:
        logger.warning("curl-cffi not installed — skipping Tier 2")
        return None

    logger.info("Tier 2 [curl-cffi] starting")

    cookies = {}
    for c in get_instagram_cookies():
        cookies[c["name"]] = c["value"]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        **_BASE_HEADERS,
    }

    try:
        async with CurlSession(impersonate="chrome124") as session:
            resp = await session.get(
                url,
                headers=headers,
                cookies=cookies,
                allow_redirects=True,
                timeout=20,
            )
            logger.info("curl-cffi: status=%d size=%d", resp.status_code, len(resp.text))

            if resp.status_code != 200:
                logger.warning("curl-cffi: non-200 status %d", resp.status_code)
                return None

            final_url = str(resp.url)
            if "accounts/login" in final_url or "challenge" in final_url:
                logger.warning("curl-cffi: login-wall redirect")
                return None

            html    = resp.text
            og      = _parse_og_tags(html)
            caption = og.get("description", "") or og.get("title", "") or _parse_jsonld(html)

            if not caption:
                logger.info("curl-cffi: no caption found in HTML")
                return None

            inline_urls = _extract_external_urls(html)
            logger.info(
                "curl-cffi: success | caption=%d chars | urls=%d",
                len(caption), len(inline_urls),
            )
            return _build_scraped_data(url, caption, [], inline_urls, "curl_cffi")

    except Exception as exc:
        logger.error("Tier 2 [curl-cffi] failed: %s", exc)
        return None


# ── Tier 3: oEmbed / public httpx fallback ────────────────────────────────────

async def _tier3_oembed(url: str) -> ScrapedData:
    """
    Official Instagram oEmbed API + httpx fallback.

    • If FACEBOOK_ACCESS_TOKEN is set → Graph API oEmbed (rich, reliable)
    • Otherwise → public /oembed endpoint (no token required)
    • Always returns a ScrapedData (may have empty caption)
    """
    logger.info("Tier 3 [oEmbed] starting")

    caption     = ""
    inline_urls: list[str] = []
    fb_token    = get_facebook_token()

    # ── A: Graph API oEmbed (with token) ──────────────────────────────────────
    if fb_token:
        oembed_url = (
            f"https://graph.facebook.com/v18.0/instagram_oembed"
            f"?url={quote(url, safe='')}&access_token={fb_token}"
            f"&fields=title,author_name,thumbnail_url,html"
        )
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(oembed_url)
                if resp.status_code == 200:
                    data    = resp.json()
                    caption = data.get("title", "") or data.get("author_name", "")
                    logger.info("oEmbed (Graph API): title=%r", caption[:60])
        except Exception as exc:
            logger.warning("oEmbed Graph API error: %s", exc)

    # ── B: Public /oembed endpoint (no token) ─────────────────────────────────
    if not caption:
        try:
            public_oembed = f"https://www.instagram.com/oembed/?url={quote(url, safe='')}&format=json"
            async with httpx.AsyncClient(timeout=10.0, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ReelScan/1.0)",
            }) as client:
                resp = await client.get(public_oembed)
                if resp.status_code == 200:
                    data    = resp.json()
                    caption = data.get("title", "") or data.get("author_name", "")
                    logger.info("oEmbed (public): title=%r", caption[:60])
        except Exception as exc:
            logger.warning("oEmbed public error: %s", exc)

    # ── C: httpx with full browser headers (last resort) ─────────────────────
    if not caption:
        cookies_dict = {c["name"]: c["value"] for c in get_instagram_cookies()}
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            **{k: v for k, v in _BASE_HEADERS.items() if k != "Origin"},
        }
        try:
            async with httpx.AsyncClient(
                headers=headers,
                cookies=cookies_dict,
                follow_redirects=True,
                timeout=18.0,
            ) as client:
                resp = await client.get(url)
                logger.info("httpx fallback: status=%d", resp.status_code)
                if resp.status_code == 200:
                    html = resp.text
                    if "accounts/login" not in str(resp.url):
                        og      = _parse_og_tags(html)
                        caption = og.get("description", "") or og.get("title", "") or _parse_jsonld(html)
                        inline_urls = _extract_external_urls(html)
                        if caption:
                            logger.info("httpx fallback: caption=%d chars", len(caption))
        except Exception as exc:
            logger.warning("httpx fallback error: %s", exc)

    tier_label = "oembed_graphapi" if (caption and fb_token) else "oembed_public" if caption else "no_data"
    logger.info(
        "Tier 3: result=%r | caption=%d chars | urls=%d",
        tier_label, len(caption), len(inline_urls),
    )
    return _build_scraped_data(url, caption, [], inline_urls, tier_label)


# ── Public entry point ────────────────────────────────────────────────────────

async def scrape_reel(url: str) -> ScrapedData:
    """
    Main scraper entry point.  Tries each tier in sequence and returns the
    first result with a non-empty caption, or the Tier-3 result as a
    graceful degradation.

    Never raises — all errors are caught internally and surfaced via
    ScrapedData.post_metadata["error"].
    """
    result: ScrapedData | None = None

    # ── Tier 1: Playwright ────────────────────────────────────────────────────
    try:
        result = await asyncio.wait_for(_tier1_playwright(url), timeout=45.0)
    except asyncio.TimeoutError:
        logger.warning("Tier 1 timeout after 45s")
        result = None
    except Exception as exc:
        logger.error("Tier 1 unexpected error: %s", exc)
        result = None

    if result and result.caption:
        logger.info("Scraper: returning Tier-1 result")
        return result

    # ── Tier 2: curl-cffi ─────────────────────────────────────────────────────
    try:
        result = await asyncio.wait_for(_tier2_curlffi(url), timeout=25.0)
    except asyncio.TimeoutError:
        logger.warning("Tier 2 timeout after 25s")
        result = None
    except Exception as exc:
        logger.error("Tier 2 unexpected error: %s", exc)
        result = None

    if result and result.caption:
        logger.info("Scraper: returning Tier-2 result")
        return result

    # ── Tier 3: oEmbed / httpx ────────────────────────────────────────────────
    try:
        result = await asyncio.wait_for(_tier3_oembed(url), timeout=20.0)
    except asyncio.TimeoutError:
        logger.warning("Tier 3 timeout after 20s")
        result = _build_scraped_data(url, "", [], [], "timeout")
    except Exception as exc:
        logger.error("Tier 3 unexpected error: %s", exc)
        result = _build_scraped_data(url, "", [], [], "error")

    if not result.caption:
        logger.warning("Scraper: all tiers failed to extract caption for %s", url)
        # Surface a clear error in metadata so the dashboard can show it
        result.post_metadata["scraper_warning"] = (
            "Could not extract caption. "
            "For best results, set INSTAGRAM_SESSIONID in environment variables. "
            "See .env.example for details."
        )

    logger.info("Scraper: returning Tier-3 result (tier=%s)", result.post_metadata.get("scrape_tier"))
    return result
