# ReelScan — System Architecture

## Overview

ReelScan is a modular pipeline application that detects Instagram Reel automation
patterns (ManyChat / DM bots) and extracts associated resources from **publicly
accessible** post data. It performs **no login bypass**, **no automated actions**,
and operates within ethical scraping boundaries.

---

## Directory Structure

```
instagram-reel-analyzer/
├── backend/
│   ├── main.py              # FastAPI app + endpoints
│   ├── models.py            # Pydantic request/response models
│   ├── scraper.py           # Playwright scraping layer
│   ├── data_processor.py    # Text cleaning & normalization
│   ├── nlp_detector.py      # Rule-based + spaCy NLP detection
│   ├── link_extractor.py    # URL extraction & resolution
│   ├── inference_engine.py  # Result assembly & inference
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── index.css
│   │   └── components/
│   │       ├── InputPanel.jsx      # URL input + demo buttons
│   │       ├── ResultPanel.jsx     # 4-case result display
│   │       ├── ConfidenceBar.jsx   # Animated score bar
│   │       ├── ResourceCard.jsx    # Resource/link display
│   │       └── ScanLines.jsx       # StatusBar + CRT overlay
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── docs/
    └── ARCHITECTURE.md     ← this file
```

---

## Pipeline Flow

```
[User] ──URL──▶ [Validate] ──▶ [Scraper] ──▶ [Processor]
                                                   │
                                                   ▼
                                           [NLP Detector]
                                                   │
                                                   ▼
                                         [Link Extractor]
                                                   │
                                                   ▼
                                        [Inference Engine]
                                                   │
                                                   ▼
                                         [API Response JSON]
                                                   │
                                                   ▼
                                         [React Dashboard]
```

---

## Module Details

### 1 · Scraper (`scraper.py`)
- **Engine**: Playwright Chromium (headless)
- **Stealth**: Custom User-Agent, automation flag disabled
- **Extracts**: Caption, comments (with lazy scroll), hashtags, bio link
- **Resource blocking**: Images/videos blocked for speed
- **Error handling**: Graceful degradation — returns empty ScrapedData on failure

### 2 · Data Processor (`data_processor.py`)
- Strips emojis, invisible/zero-width Unicode
- NFKC normalization (handles full-width chars)
- Keyword normalization: "e-book" → "ebook", "PD F" → "pdf"
- Spam detection + deduplication of comments
- Rebuilds clean `raw_text_corpus` for NLP

### 3 · NLP Detector (`nlp_detector.py`)
- **Rule engine**: 7 named regex patterns covering all common ManyChat flows
- **Keyword density bonus**: Weighted by resource word frequency
- **Optional spaCy boost**: Dependency parse checks for imperative verb + resource noun
- **Confidence scoring**: 0–100, threshold at 20 for `automation_detected = true`
- **Model flag**: Reports `rule_based` or `rule_based + spaCy`

#### Pattern Catalogue
| ID | Pattern | Base Score |
|----|---------|------------|
| comment_trigger_keyword | `comment 'link'` style | 35 |
| dm_trigger | `DM me 'guide'` style | 30 |
| bio_link_reference | `link in bio` | 20 |
| get_free_resource | `get the free pdf` | 15 |
| save_post_cta | `save this post` | 10 |
| want_comment_below | `want the ebook? comment` | 25 |
| manychat_pattern | explicit ManyChat reference | 40 |

### 4 · Link Extractor (`link_extractor.py`)
- Regex URL scan of caption + comments (first 100) + bio
- Deduplication by exact URL
- Concurrent resolution via `asyncio.Semaphore(10)`
- Redirect chain following: bit.ly, t.co, linktr.ee, etc.
- File type detection: extension-first, then HTTP Content-Type header
- Supported file types: PDF, DOC, DOCX, ZIP

### 5 · Inference Engine (`inference_engine.py`)
- Resolves one of 4 `ResultCase` values
- Picks best action template based on trigger keyword
- Builds human-readable `analysis_summary`
- Assembles final `AnalyzeResponse`

---

## API Reference

### `POST /analyze`
```json
// Request
{ "url": "https://www.instagram.com/reel/XXXXX/" }

// Response
{
  "automation_detected": true,
  "result_case": "file_found | link_found | automation_detected | no_automation",
  "trigger_keywords": ["guide"],
  "confidence_score": 85,
  "matched_patterns": ["comment_trigger_keyword"],
  "file_type": "pdf | doc | docx | zip | none",
  "download_link": "https://example.com/file.pdf",
  "extracted_links": [],
  "suggested_action": "Comment 'guide' on the reel...",
  "post_url": "https://www.instagram.com/reel/XXXXX/",
  "analysis_summary": "...",
  "processing_time_ms": 1240,
  "error": null
}
```

### `GET /demo/{case}`
Returns canned responses for UI testing.
Valid cases: `file`, `link`, `automation`, `none`

### `GET /health`
Returns `{ "status": "ok", "version": "1.0.0" }`

---

## Dashboard — 4 Result Cases

| Case | Trigger | UI |
|------|---------|----|
| FILE_FOUND | File URL extracted | Download + Preview buttons |
| LINK_FOUND | Plain URL extracted | Copy + Open buttons |
| AUTOMATION_DETECTED | Pattern matched, no URL | Suggestion box + keyword chips |
| NO_AUTOMATION | Score < 20 | "No pattern detected" |

---

## Legal & Ethical Considerations

| Constraint | Implementation |
|------------|----------------|
| No auth bypass | Playwright loads public page only; no login forms, no cookies injected |
| No automated actions | Read-only pipeline; no POST to Instagram, no DMs sent |
| No CAPTCHA bypass | If Instagram blocks with CAPTCHA, scraper returns empty data gracefully |
| Public data only | Equivalent to reading a public web page in a browser |
| Rate limiting | No concurrent scraping; one request per user action |
| robots.txt spirit | Does not scrape private profiles or stories |
| Data retention | No scraped data stored; response is ephemeral per request |

> **Users** are responsible for ensuring their use complies with Instagram's
> Terms of Service and applicable laws in their jurisdiction. This tool is
> designed for research, OSINT, and educational purposes.

---

## Setup & Running

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
# Optional NLP:
python -m spacy download en_core_web_sm
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev   # → http://localhost:3000
```

---

## Extending the System

### Adding a new NLP pattern
In `nlp_detector.py`, append to `RULE_PATTERNS`:
```python
(
    "your_pattern_name",
    re.compile(r"your regex here", re.IGNORECASE),
    score_0_to_40,
),
```

### Adding a new file type
In `link_extractor.py`, add to `FILE_EXTENSIONS`:
```python
".ppt": FileType.UNKNOWN,
```
And add the enum member to `models.py → FileType`.

### Swapping to a transformer model
In `nlp_detector.py`, replace `_spacy_boost()` with a call to any
`sentence-transformers` model. The function signature returns `int` (bonus score),
so the rest of the pipeline is unaffected.
