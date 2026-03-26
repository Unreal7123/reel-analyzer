"""
ReelScan Agent Modules
======================
Each module corresponds to a specialized agent in the analysis pipeline:
- scraper          → Instagram Extractor Agent
- data_processor   → Data Cleaner Agent
- nlp_detector     → NLP Detector Agent
- link_extractor   → Link Extractor Agent
- inference_engine → Response Builder Agent
"""

from .scraper import scrape_reel
from .data_processor import process_scraped_data
from .nlp_detector import detect_automation
from .link_extractor import extract_resources
from .inference_engine import build_response

__all__ = [
    "scrape_reel",
    "process_scraped_data",
    "detect_automation",
    "extract_resources",
    "build_response",
]
