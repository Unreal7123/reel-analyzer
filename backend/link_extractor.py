"""
Link & File Extraction Layer

Extracts URLs from caption, comments, and bio link.
Resolves shortened URLs (bit.ly, t.co, linktree, etc.) and follows redirect
chains to identify final destinations and file types.

Only performs HTTP HEAD/GET on public URLs. No authentication involved.
"""

import re
import logging
import asyncio
from urllib.parse import urlparse
import httpx

from models import ScrapedData, ExtractedResource, FileType

logger = logging.getLogger(__name__)

# ─── Patterns ──────────────────────────────────────────────────────────────────

URL_PATTERN = re.compile(
    r"https?://[^\s\u200b\u200c\u200d\ufeff\"'<>)\]]+",
    re.IGNORECASE,
)

# Instagram obfuscates links in captions — also catch common transformations
OBFUSCATED_PATTERNS = [
    re.compile(r"\b(?:bit\.ly|tinyurl\.com|t\.co|ow\.ly|goo\.gl|rb\.gy|"
               r"shorturl\.at|cutt\.ly|linktr\.ee|linktree|link\.tree)\b",
               re.IGNORECASE),
]

FILE_EXTENSIONS: dict[str, FileType] = {
    ".pdf": FileType.PDF,
    ".doc": FileType.DOC,
    ".docx": FileType.DOCX,
    ".zip": FileType.ZIP,
}

REDIRECT_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "ow.ly", "goo.gl", "rb.gy",
    "shorturl.at", "cutt.ly", "linktr.ee", "link.tree",
}

# ─── Helpers ───────────────────────────────────────────────────────────────────

def _detect_file_type(url: str) -> FileType:
    path = urlparse(url.lower()).path
    for ext, ft in FILE_EXTENSIONS.items():
        if path.endswith(ext):
            return ft
    return FileType.NONE


def _is_redirect_domain(url: str) -> bool:
    host = urlparse(url).netloc.lstrip("www.")
    return host in REDIRECT_DOMAINS


async def _resolve_url(url: str, max_redirects: int = 10) -> str:
    """Follow redirect chain and return final URL."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=max_redirects,
            timeout=8.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LinkResolver/1.0)"},
        ) as client:
            resp = await client.head(url)
            return str(resp.url)
    except Exception as e:
        logger.debug(f"URL resolution failed for {url}: {e}")
        return url


async def _check_content_type(url: str) -> FileType:
    """Check Content-Type header to determine if URL serves a file."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=10,
            timeout=8.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LinkResolver/1.0)"},
        ) as client:
            resp = await client.head(url)
            ct = resp.headers.get("content-type", "").lower()
            if "pdf" in ct:
                return FileType.PDF
            if "zip" in ct or "octet-stream" in ct:
                return FileType.ZIP
            if "msword" in ct or "officedocument" in ct:
                return FileType.DOCX
    except Exception:
        pass
    return FileType.NONE


# ─── Main extractor ────────────────────────────────────────────────────────────

async def extract_resources(data: ScrapedData) -> list[ExtractedResource]:
    """
    Extract and resolve all URLs from scraped data.
    Returns a list of ExtractedResource objects with resolved URLs + file types.
    """
    candidates: list[tuple[str, str]] = []  # (raw_url, source)

    # Caption
    for m in URL_PATTERN.finditer(data.caption):
        candidates.append((m.group(), "caption"))

    # Comments (limit to first 100 to avoid abuse)
    for comment in data.comments[:100]:
        for m in URL_PATTERN.finditer(comment):
            candidates.append((m.group(), "comment"))

    # Bio link
    if data.bio_link:
        candidates.append((data.bio_link, "bio"))

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for url, src in candidates:
        if url not in seen:
            seen.add(url)
            unique.append((url, src))

    # Resolve concurrently (max 10 at a time)
    sem = asyncio.Semaphore(10)

    async def _process(url: str, source: str) -> ExtractedResource:
        async with sem:
            resolved = url
            if _is_redirect_domain(url):
                resolved = await _resolve_url(url)

            # File type from extension first, then Content-Type header
            ft = _detect_file_type(resolved)
            if ft == FileType.NONE:
                ft = await _check_content_type(resolved)

            return ExtractedResource(
                url=url,
                file_type=ft,
                resolved_url=resolved if resolved != url else None,
                source=source,
            )

    tasks = [_process(url, src) for url, src in unique]
    results: list[ExtractedResource] = await asyncio.gather(*tasks)
    return results
