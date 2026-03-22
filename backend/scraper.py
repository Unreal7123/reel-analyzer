"""
Scraper Layer — uses Playwright to extract publicly visible data from
Instagram Reels without authentication. Only reads data rendered in the
browser's public view.

Legal note: Only scrapes publicly accessible content. Does NOT bypass
login walls, CAPTCHA, or any authentication mechanism.
"""

import asyncio
import re
import logging
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser

from models import ScrapedData

logger = logging.getLogger(__name__)

# ── Selectors (fragile — update when Instagram changes their DOM) ──────────
CAPTION_SELECTORS = [
    "h1._aacl",
    "div._a9zs span",
    "div[data-testid='post-comment-root'] span",
    "article div._a9zs",
    "span._aacl._aaco._aacu._aacx._aad7._aade",
]

COMMENT_SELECTORS = [
    "div._a9zs span._aacl",
    "ul._a9ym li span._aacl",
    "div[role='button'] span._aacl",
]

HASHTAG_PATTERN = re.compile(r"#[\w\u00C0-\u024F\u0400-\u04FF]+", re.UNICODE)
URL_PATTERN = re.compile(
    r"https?://[^\s\u200b\u200c\u200d\ufeff\"'>)]+", re.IGNORECASE
)


async def _scroll_comments(page: Page, max_scrolls: int = 5) -> None:
    """Scroll comment section to trigger lazy-loading."""
    comment_section = await page.query_selector("ul._a9ym")
    if not comment_section:
        return
    for _ in range(max_scrolls):
        await comment_section.evaluate("el => el.scrollTop += el.scrollHeight")
        await asyncio.sleep(0.8)


async def _click_load_more(page: Page) -> None:
    """Click 'Load more comments' buttons if present."""
    while True:
        btn = await page.query_selector("button._abl-")
        if btn:
            await btn.click()
            await asyncio.sleep(1.0)
        else:
            break


async def _extract_text(page: Page, selectors: list[str]) -> list[str]:
    texts: list[str] = []
    for sel in selectors:
        elements = await page.query_selector_all(sel)
        for el in elements:
            t = (await el.inner_text()).strip()
            if t:
                texts.append(t)
        if texts:
            break
    return texts


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


async def scrape_reel(url: str, headless: bool = True) -> ScrapedData:
    """
    Main entry point. Launches a stealth Playwright browser, navigates to
    the public Instagram Reel URL, and extracts structured data.

    Returns ScrapedData. On any failure returns an empty ScrapedData so the
    pipeline can continue with partial data rather than crashing.
    """
    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await context.new_page()

        # Block unnecessary resources to speed up scraping
        await page.route(
            "**/*.{png,jpg,jpeg,gif,webp,mp4,woff2}",
            lambda r: r.abort(),
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2)  # let JS hydrate

            # ── Caption ──────────────────────────────────────────────────
            caption_parts = await _extract_text(page, CAPTION_SELECTORS)
            caption = " ".join(caption_parts[:1]) if caption_parts else ""

            # ── Comments ─────────────────────────────────────────────────
            await _scroll_comments(page)
            await _click_load_more(page)
            raw_comments = await _extract_text(page, COMMENT_SELECTORS)
            comments = _deduplicate(raw_comments)

            # ── Hashtags ─────────────────────────────────────────────────
            full_text = caption + " " + " ".join(comments)
            hashtags = list(set(HASHTAG_PATTERN.findall(full_text)))

            # ── Bio link (from author profile link in post) ───────────────
            bio_link: Optional[str] = None
            try:
                profile_link_el = await page.query_selector(
                    "a[href*='/p/'][href*='tagged'] ~ a, header a[role='link']"
                )
                if profile_link_el:
                    href = await profile_link_el.get_attribute("href")
                    if href:
                        bio_page = await context.new_page()
                        profile_url = (
                            f"https://www.instagram.com{href}"
                            if href.startswith("/")
                            else href
                        )
                        await bio_page.goto(
                            profile_url,
                            wait_until="domcontentloaded",
                            timeout=20_000,
                        )
                        await asyncio.sleep(1.5)
                        link_el = await bio_page.query_selector(
                            "a[href*='linktree'], a[href*='linktr.ee'], "
                            "a[rel='me nofollow noopener noreferrer']"
                        )
                        if link_el:
                            bio_link = await link_el.get_attribute("href")
                        await bio_page.close()
            except Exception as e:
                logger.warning(f"Bio link extraction failed: {e}")

            # ── Metadata ─────────────────────────────────────────────────
            post_metadata = {
                "url": url,
                "page_title": await page.title(),
            }

            # ── Raw corpus ───────────────────────────────────────────────
            raw_corpus = "\n".join([caption] + comments)

            return ScrapedData(
                caption=caption,
                hashtags=hashtags,
                comments=comments,
                bio_link=bio_link,
                post_metadata=post_metadata,
                raw_text_corpus=raw_corpus,
            )

        except Exception as e:
            logger.error(f"Scraping failed for {url}: {e}")
            return ScrapedData(
                post_metadata={"url": url, "error": str(e)},
                raw_text_corpus="",
            )
        finally:
            await browser.close()