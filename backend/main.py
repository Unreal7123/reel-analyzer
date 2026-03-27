"""
ReelScan FastAPI Application
============================

Pipeline (unchanged from v1):
  POST /analyze  →  scrape_reel → process_scraped_data → detect_automation
                 →  extract_resources → build_response

New endpoints:
  GET  /session-status   — shows which scrape tier will be used
  GET  /health           — liveness check

All pipeline modules (link_extractor, nlp_detector, inference_engine,
data_processor) are imported unchanged.
"""

import os
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import AnalyzeRequest, AnalyzeResponse, NLPResult
from agents.scraper          import scrape_reel
from agents.data_processor   import process_scraped_data
from agents.nlp_detector     import detect_automation
from agents.link_extractor   import extract_resources
from agents.inference_engine import build_response
from agents.session_manager  import session_status

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── CORS ──────────────────────────────────────────────────────────────────────

_CORS_ORIGINS = (
    os.getenv("CORS_ORIGINS", "").split(",")
    if os.getenv("CORS_ORIGINS")
    else ["http://localhost", "http://localhost:3000", "http://localhost:5173", "http://127.0.0.1"]
)

# ── Application ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    status = session_status()
    logger.info("ReelScan API starting")
    logger.info("Session status: %s", status["scrape_tier_available"])
    if not status["has_sessionid"]:
        logger.warning(
            "INSTAGRAM_SESSIONID not set — caption extraction may be limited. "
            "See .env.example for setup instructions."
        )
    yield
    logger.info("ReelScan API shutting down")


app = FastAPI(
    title="ReelScan",
    version="2.0.0",
    lifespan=lifespan,
    root_path=os.getenv("ROOT_PATH", ""),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.(onrender|railway|vercel|netlify)\.app",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# ── Main analysis endpoint ────────────────────────────────────────────────────

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_reel(request: AnalyzeRequest) -> AnalyzeResponse:
    t0  = time.monotonic()
    url = request.url
    logger.info("Analyzing: %s", url)

    error:  str | None = None
    scraped = None

    try:
        # ── Step 1: Scrape ────────────────────────────────────────────────────
        scraped = await scrape_reel(url)

        # Surface scraper warnings as soft errors (pipeline continues)
        if "scraper_warning" in (scraped.post_metadata or {}):
            error = scraped.post_metadata["scraper_warning"]
            logger.warning("Scraper warning: %s", error)

        # ── Step 2: Clean + normalise ─────────────────────────────────────────
        processed = process_scraped_data(scraped)

        # ── Step 3: NLP detection ─────────────────────────────────────────────
        nlp_result = detect_automation(processed)

        # ── Step 4: Link extraction ───────────────────────────────────────────
        resources = await extract_resources(processed)

    except Exception as exc:
        logger.exception("Pipeline error: %s", exc)
        nlp_result = NLPResult()
        resources  = []
        error      = f"Pipeline error: {exc}"

    elapsed  = int((time.monotonic() - t0) * 1000)
    metadata = scraped.post_metadata if scraped else {}

    response = build_response(
        post_url=url,
        nlp=nlp_result,
        resources=resources,
        metadata=metadata,
        processing_time_ms=elapsed,
        error=error,
    )

    logger.info(
        "Done %dms | tier=%s | case=%s | confidence=%d%%",
        elapsed,
        metadata.get("scrape_tier", "unknown"),
        response.result_case,
        response.confidence_score,
    )
    return response


# ── Demo cases ────────────────────────────────────────────────────────────────

_DEMOS = {
    "file": {
        "automation_detected": True, "result_case": "file_found",
        "trigger_keywords": ["pdf", "guide"], "confidence_score": 92,
        "matched_patterns": ["comment_trigger_keyword", "get_free_resource"],
        "spam_signals": ["'pdf' repeated 47× in comments", "Automation emoji 📥 used 31× in comments"],
        "spam_analysis": {
            "top_comments": [{"text": "pdf", "count": 47}, {"text": "guide", "count": 23}, {"text": "send me", "count": 18}],
            "top_emojis":   [{"emoji": "📥", "count": 31}, {"emoji": "🔗", "count": 24}, {"emoji": "✅", "count": 19}],
            "spam_score": 78, "total_comments": 342,
        },
        "file_type": "pdf", "download_link": "https://example.com/free-guide.pdf",
        "extracted_links": [], "suggested_action": None,
        "post_url": "https://www.instagram.com/reel/demo/",
        "analysis_summary": "Automated PDF distribution detected (92% confidence). Analyzed 342 comments (78% repetition rate).",
        "processing_time_ms": 4200, "error": None,
    },
    "link": {
        "automation_detected": True, "result_case": "link_found",
        "trigger_keywords": ["link", "resource"], "confidence_score": 78,
        "matched_patterns": ["bio_link_reference", "get_free_resource"],
        "spam_signals": ["'link' repeated 29× in comments", "Automation emoji 🔗 used 41× in comments"],
        "spam_analysis": {
            "top_comments": [{"text": "link please", "count": 29}, {"text": "send link", "count": 17}],
            "top_emojis":   [{"emoji": "🔗", "count": 41}, {"emoji": "👇", "count": 28}],
            "spam_score": 55, "total_comments": 187,
        },
        "file_type": "none", "download_link": None,
        "extracted_links": ["https://linktr.ee/example_creator"], "suggested_action": None,
        "post_url": "https://www.instagram.com/reel/demo/",
        "analysis_summary": "Automation pattern detected (78% confidence). 1 resource link extracted. Analyzed 187 comments (55% repetition rate).",
        "processing_time_ms": 3100, "error": None,
    },
    "automation": {
        "automation_detected": True, "result_case": "automation_detected",
        "trigger_keywords": ["ebook", "guide"], "confidence_score": 65,
        "matched_patterns": ["comment_trigger_keyword", "manychat_pattern"],
        "spam_signals": ["'ebook' repeated 38× in comments", "Automation emoji 📩 used 44× in comments"],
        "spam_analysis": {
            "top_comments": [{"text": "ebook", "count": 38}, {"text": "yes please", "count": 22}, {"text": "interested", "count": 15}],
            "top_emojis":   [{"emoji": "📩", "count": 44}, {"emoji": "🎁", "count": 33}, {"emoji": "💌", "count": 21}],
            "spam_score": 71, "total_comments": 256,
        },
        "file_type": "none", "download_link": None, "extracted_links": [],
        "suggested_action": "Comment 'ebook' on the reel to automatically receive a free eBook via DM",
        "post_url": "https://www.instagram.com/reel/demo/",
        "analysis_summary": "Automation trigger detected (65% confidence) via keywords: 'ebook', 'guide'. No direct link — likely DM bot. Analyzed 256 comments (71% repetition rate).",
        "processing_time_ms": 5800, "error": None,
    },
    "none": {
        "automation_detected": False, "result_case": "no_automation",
        "trigger_keywords": [], "confidence_score": 5,
        "matched_patterns": [], "spam_signals": [],
        "spam_analysis": {
            "top_comments": [], "top_emojis": [{"emoji": "❤️", "count": 12}, {"emoji": "🔥", "count": 8}],
            "spam_score": 8, "total_comments": 43,
        },
        "file_type": "none", "download_link": None, "extracted_links": [],
        "suggested_action": None,
        "post_url": "https://www.instagram.com/reel/demo/",
        "analysis_summary": "No automation patterns detected. Analyzed 43 comments (8% repetition rate).",
        "processing_time_ms": 2900, "error": None,
    },
}


@app.get("/demo/{case}")
async def demo(case: str):
    if case not in _DEMOS:
        raise HTTPException(404, detail=f"Unknown demo case. Choose from: {list(_DEMOS.keys())}")
    return JSONResponse(_DEMOS[case])


# ── Utility endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status":  "ok",
        "version": "2.0.0",
        "session": session_status(),
    }


@app.get("/session-status")
async def get_session_status():
    """
    Returns which scraping tier will be used and what's configured.
    Useful for debugging deployment configuration.
    """
    return session_status()


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}"},
    )
