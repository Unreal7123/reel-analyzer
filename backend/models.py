from pydantic import BaseModel, field_validator
from typing import Optional, List
from enum import Enum


class FileType(str, Enum):
    PDF  = "pdf"
    DOC  = "doc"
    DOCX = "docx"
    ZIP  = "zip"
    UNKNOWN = "unknown"
    NONE = "none"


class ResultCase(str, Enum):
    FILE_FOUND          = "file_found"
    LINK_FOUND          = "link_found"
    AUTOMATION_DETECTED = "automation_detected"
    NO_AUTOMATION       = "no_automation"


class AnalyzeRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_instagram_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("http"):
            v = "https://" + v
        allowed = ["instagram.com/reel/", "instagram.com/p/", "instagr.am/"]
        if not any(k in v for k in allowed):
            raise ValueError(
                "URL must be a valid Instagram Reel or Post URL "
                "(e.g. https://www.instagram.com/reel/XXXXX/)"
            )
        return v


class TopComment(BaseModel):
    text:  str
    count: int


class TopEmoji(BaseModel):
    emoji: str
    count: int


class SpamAnalysis(BaseModel):
    top_comments:   List[TopComment] = []
    top_emojis:     List[TopEmoji]   = []
    spam_score:     int = 0          # 0-100 — how much comment repetition
    total_comments: int = 0


class ScrapedData(BaseModel):
    caption:         str              = ""
    hashtags:        List[str]        = []
    comments:        List[str]        = []
    bio_link:        Optional[str]    = None
    post_metadata:   dict             = {}
    raw_text_corpus: str              = ""


class NLPResult(BaseModel):
    automation_detected: bool       = False
    trigger_keywords:    List[str]  = []
    confidence_score:    int        = 0
    matched_patterns:    List[str]  = []
    spam_signals:        List[str]  = []   # human-readable spam comment signals
    nlp_model_used:      str        = "rule_based"


class ExtractedResource(BaseModel):
    url:          str
    file_type:    FileType      = FileType.NONE
    resolved_url: Optional[str] = None
    source:       str           = "unknown"


class AnalyzeResponse(BaseModel):
    # Core
    automation_detected: bool
    result_case:         ResultCase

    # NLP
    trigger_keywords:  List[str] = []
    confidence_score:  int       = 0
    matched_patterns:  List[str] = []
    spam_signals:      List[str] = []

    # Spam / comment analysis
    spam_analysis:     SpamAnalysis = SpamAnalysis()

    # Resources
    file_type:      FileType      = FileType.NONE
    download_link:  Optional[str] = None
    extracted_links: List[str]   = []
    all_resources:  List[ExtractedResource] = []

    # Inference
    suggested_action: Optional[str] = None

    # Meta
    post_url:           str           = ""
    analysis_summary:   str           = ""
    processing_time_ms: int           = 0
    error:              Optional[str] = None