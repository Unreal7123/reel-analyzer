"""
Instagram Reel Automation Analyzer — FastAPI Backend

Endpoints:
  POST /analyze        — full pipeline
  GET  /demo/{case}    — demo responses for UI testing
  GET  /health         — health check
"""

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s")
logger = logging.getLogger(__name__)

_CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = (
    _CORS_ORIGINS_ENV.split(",") if _CORS_ORIGINS_ENV
    else ["http://localhost", "http://localhost:3000", "http://localhost:5173", "http://127.0.0.1"]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ReelScan API starting — CORS origins: %s", ALLOWED_ORIGINS)
    yield
    logger.info("ReelScan API stopped.")

app = FastAPI(
    title="ReelScan",
    version="1.0.0",
    lifespan=lifespan,
    root_path=os.getenv("ROOT_PATH", ""),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.(onrender|railway|vercel|netlify)\.app",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

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
        logger.exception(f"Pipeline error for {url}: {exc}")
        from models import NLPResult
        nlp_result = NLPResult()
        resources  = []
        error = str(exc)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    response = build_response(post_url=url, nlp=nlp_result, resources=resources,
                              processing_time_ms=elapsed_ms, error=error)
    logger.info(f"Done in {elapsed_ms}ms | case={response.result_case} | confidence={response.confidence_score}")
    return response

_DEMOS = {
    "file":       {"automation_detected":True,"result_case":"file_found","trigger_keywords":["pdf","guide"],"confidence_score":92,"matched_patterns":["comment_trigger_keyword","get_free_resource"],"file_type":"pdf","download_link":"https://example.com/free-guide.pdf","extracted_links":[],"suggested_action":None,"post_url":"https://www.instagram.com/reel/demo/","analysis_summary":"Automated PDF distribution detected with 92% confidence. A direct file link was found and extracted.","processing_time_ms":1240,"error":None},
    "link":       {"automation_detected":True,"result_case":"link_found","trigger_keywords":["link","resource"],"confidence_score":78,"matched_patterns":["bio_link_reference","get_free_resource"],"file_type":"none","download_link":None,"extracted_links":["https://linktr.ee/example_creator"],"suggested_action":None,"post_url":"https://www.instagram.com/reel/demo/","analysis_summary":"Automation pattern detected (78% confidence). 1 resource link extracted.","processing_time_ms":980,"error":None},
    "automation": {"automation_detected":True,"result_case":"automation_detected","trigger_keywords":["ebook","guide"],"confidence_score":65,"matched_patterns":["comment_trigger_keyword","manychat_pattern"],"file_type":"none","download_link":None,"extracted_links":[],"suggested_action":"Comment 'ebook' on the reel to automatically receive a free eBook via DM","post_url":"https://www.instagram.com/reel/demo/","analysis_summary":"Automation trigger detected (65% confidence). No direct link found — likely distributed via DM bot.","processing_time_ms":760,"error":None},
    "none":       {"automation_detected":False,"result_case":"no_automation","trigger_keywords":[],"confidence_score":5,"matched_patterns":[],"file_type":"none","download_link":None,"extracted_links":[],"suggested_action":None,"post_url":"https://www.instagram.com/reel/demo/","analysis_summary":"No automation patterns detected.","processing_time_ms":430,"error":None},
}

@app.get("/demo/{case}")
async def demo_response(case: str):
    if case not in _DEMOS:
        raise HTTPException(404, detail=f"Unknown demo case '{case}'. Choose: {list(_DEMOS.keys())}")
    return JSONResponse(_DEMOS[case])

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
