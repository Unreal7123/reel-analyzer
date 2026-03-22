import os, time, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import AnalyzeRequest, AnalyzeResponse
from scraper import scrape_reel
from data_processor import process_scraped_data
from nlp_detector import detect_automation
from link_extractor import extract_resources
from inference_engine import build_response

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s")
logger = logging.getLogger(__name__)

_CORS = os.getenv("CORS_ORIGINS","").split(",") if os.getenv("CORS_ORIGINS") else [
    "http://localhost","http://localhost:3000","http://localhost:5173","http://127.0.0.1"
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ReelScan API starting")
    yield

app = FastAPI(title="ReelScan", version="1.0.0", lifespan=lifespan,
              root_path=os.getenv("ROOT_PATH",""))

app.add_middleware(CORSMiddleware, allow_origins=_CORS,
    allow_origin_regex=r"https://.*\.(onrender|railway|vercel|netlify)\.app",
    allow_credentials=False, allow_methods=["GET","POST","OPTIONS"],
    allow_headers=["Content-Type"])

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_reel(request: AnalyzeRequest) -> AnalyzeResponse:
    t0 = time.monotonic()
    url = request.url
    logger.info(f"Analyzing: {url}")
    error = None
    try:
        scraped    = await scrape_reel(url)
        processed  = process_scraped_data(scraped)
        nlp_result = detect_automation(processed)
        resources  = await extract_resources(processed)
    except Exception as exc:
        logger.exception(f"Pipeline error: {exc}")
        from models import NLPResult
        nlp_result = NLPResult(); resources = []; error = str(exc)
        scraped = None

    elapsed = int((time.monotonic() - t0) * 1000)
    metadata = scraped.post_metadata if scraped else {}
    response = build_response(post_url=url, nlp=nlp_result, resources=resources,
                              metadata=metadata, processing_time_ms=elapsed, error=error)
    logger.info(f"Done {elapsed}ms | {response.result_case} | {response.confidence_score}%")
    return response

_DEMOS = {
    "file": {
        "automation_detected": True, "result_case": "file_found",
        "trigger_keywords": ["pdf","guide"], "confidence_score": 92,
        "matched_patterns": ["comment_trigger_keyword","get_free_resource"],
        "spam_signals": ["'pdf' repeated 47× in comments","Automation emoji 📥 used 31× in comments"],
        "spam_analysis": {
            "top_comments": [{"text":"pdf","count":47},{"text":"guide","count":23},{"text":"send me","count":18}],
            "top_emojis": [{"emoji":"📥","count":31},{"emoji":"🔗","count":24},{"emoji":"✅","count":19}],
            "spam_score": 78, "total_comments": 342
        },
        "file_type": "pdf", "download_link": "https://example.com/free-guide.pdf",
        "extracted_links": [], "suggested_action": None,
        "post_url": "https://www.instagram.com/reel/demo/",
        "analysis_summary": "Automated PDF distribution detected (92% confidence). Analyzed 342 comments (78% repetition rate).",
        "processing_time_ms": 4200, "error": None
    },
    "link": {
        "automation_detected": True, "result_case": "link_found",
        "trigger_keywords": ["link","resource"], "confidence_score": 78,
        "matched_patterns": ["bio_link_reference","get_free_resource"],
        "spam_signals": ["'link' repeated 29× in comments","Automation emoji 🔗 used 41× in comments"],
        "spam_analysis": {
            "top_comments": [{"text":"link please","count":29},{"text":"send link","count":17}],
            "top_emojis": [{"emoji":"🔗","count":41},{"emoji":"👇","count":28}],
            "spam_score": 55, "total_comments": 187
        },
        "file_type": "none", "download_link": None,
        "extracted_links": ["https://linktr.ee/example_creator"],
        "suggested_action": None,
        "post_url": "https://www.instagram.com/reel/demo/",
        "analysis_summary": "Automation pattern detected (78% confidence). 1 resource link extracted. Analyzed 187 comments (55% repetition rate).",
        "processing_time_ms": 3100, "error": None
    },
    "automation": {
        "automation_detected": True, "result_case": "automation_detected",
        "trigger_keywords": ["ebook","guide"], "confidence_score": 65,
        "matched_patterns": ["comment_trigger_keyword","manychat_pattern"],
        "spam_signals": ["'ebook' repeated 38× in comments","Automation emoji 📩 used 44× in comments"],
        "spam_analysis": {
            "top_comments": [{"text":"ebook","count":38},{"text":"yes please","count":22},{"text":"interested","count":15}],
            "top_emojis": [{"emoji":"📩","count":44},{"emoji":"🎁","count":33},{"emoji":"💌","count":21}],
            "spam_score": 71, "total_comments": 256
        },
        "file_type": "none", "download_link": None, "extracted_links": [],
        "suggested_action": "Comment 'ebook' on the reel to automatically receive a free eBook via DM",
        "post_url": "https://www.instagram.com/reel/demo/",
        "analysis_summary": "Automation trigger detected (65% confidence) via keywords: 'ebook', 'guide'. No direct link — likely DM bot. Analyzed 256 comments (71% repetition rate).",
        "processing_time_ms": 5800, "error": None
    },
    "none": {
        "automation_detected": False, "result_case": "no_automation",
        "trigger_keywords": [], "confidence_score": 5,
        "matched_patterns": [], "spam_signals": [],
        "spam_analysis": {
            "top_comments": [], "top_emojis": [{"emoji":"❤️","count":12},{"emoji":"🔥","count":8}],
            "spam_score": 8, "total_comments": 43
        },
        "file_type": "none", "download_link": None, "extracted_links": [],
        "suggested_action": None,
        "post_url": "https://www.instagram.com/reel/demo/",
        "analysis_summary": "No automation patterns detected. Analyzed 43 comments (8% repetition rate).",
        "processing_time_ms": 2900, "error": None
    },
}

@app.get("/demo/{case}")
async def demo(case: str):
    if case not in _DEMOS:
        raise HTTPException(404, detail=f"Unknown case. Choose: {list(_DEMOS.keys())}")
    return JSONResponse(_DEMOS[case])

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}