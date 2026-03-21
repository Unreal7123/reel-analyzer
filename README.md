# 🔍 ReelScan — Instagram Reel Automation Detector

> Detect ManyChat / DM-bot automation patterns in public Instagram Reels.  
> Extracts links, files, and infers trigger flows — **no login, no automation, public data only**.

![ReelScan Dashboard](https://img.shields.io/badge/stack-FastAPI%20%2B%20React-00ff9f?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
![Python](https://img.shields.io/badge/python-3.11%2B-yellow?style=flat-square)
![Node](https://img.shields.io/badge/node-18%2B-green?style=flat-square)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎯 Pattern Detection | 7 NLP rule patterns for ManyChat / DM-bot flows |
| 📄 File Extraction | PDF, DOC, ZIP detection + download links |
| 🔗 Link Resolution | Follows bit.ly, linktr.ee, t.co redirect chains |
| 🤖 Inference Engine | Generates suggested action when no direct link exists |
| 📊 Confidence Score | 0–100 score with weighted rule matching |
| ⚡ 4 Result Cases | File Found / Link Found / Automation / No Pattern |

---

## 🗂 Project Structure

```
reelscan/
├── backend/                  # Python FastAPI API
│   ├── main.py               # API routes + demo endpoints
│   ├── models.py             # Pydantic schemas
│   ├── scraper.py            # Playwright scraping layer
│   ├── data_processor.py     # Text cleaning + normalization
│   ├── nlp_detector.py       # Rule-based + spaCy NLP
│   ├── link_extractor.py     # URL extraction + redirect resolver
│   ├── inference_engine.py   # Result assembly + inference
│   └── requirements.txt
├── frontend/                 # React + Vite dashboard
│   ├── src/
│   │   ├── App.jsx
│   │   ├── index.css         # Dark terminal aesthetic
│   │   └── components/
│   │       ├── InputPanel.jsx
│   │       ├── ResultPanel.jsx
│   │       ├── ConfidenceBar.jsx
│   │       └── ScanLines.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml        # One-command full-stack launch
├── Dockerfile.backend
├── Dockerfile.frontend
├── nginx.conf                # Reverse proxy config
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start

### Option A — Docker (Recommended)

```bash
git clone https://github.com/YOUR_USERNAME/reelscan.git
cd reelscan
docker compose up --build
```

Open → **http://localhost** (frontend) and **http://localhost/api** (backend)

---

### Option B — Manual

#### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
# Optional: better NLP
python -m spacy download en_core_web_sm

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev     # → http://localhost:3000
```

---

## 🌐 Deploy to the Web

### Render.com (Free Tier)

**Backend (Web Service)**
1. Connect your GitHub repo
2. Runtime: **Python 3**
3. Build command: `pip install -r backend/requirements.txt && playwright install chromium`
4. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

**Frontend (Static Site)**
1. Build command: `cd frontend && npm install && npm run build`
2. Publish directory: `frontend/dist`
3. Set env var: `VITE_API_URL=https://your-backend.onrender.com`

---

### Railway

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up
```

---

### VPS / Self-hosted

```bash
git clone https://github.com/YOUR_USERNAME/reelscan.git
cd reelscan
docker compose -f docker-compose.yml up -d
```

---

## 📡 API Reference

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
  "file_type": "pdf",
  "download_link": "https://example.com/file.pdf",
  "extracted_links": [],
  "suggested_action": "Comment 'guide' on the reel...",
  "analysis_summary": "...",
  "processing_time_ms": 1240
}
```

### `GET /demo/{case}`

Returns a canned response for UI testing.  
Cases: `file` · `link` · `automation` · `none`

### `GET /health`

```json
{ "status": "ok", "version": "1.0.0" }
```

---

## 🧠 NLP Pattern Catalogue

| Rule ID | Example Trigger | Base Score |
|---|---|---|
| `comment_trigger_keyword` | *"comment 'link' below"* | 35 |
| `dm_trigger` | *"DM me 'guide'"* | 30 |
| `want_comment_below` | *"want the ebook? comment"* | 25 |
| `bio_link_reference` | *"free pdf in bio"* | 20 |
| `get_free_resource` | *"grab the free template"* | 15 |
| `save_post_cta` | *"save this post"* | 10 |
| `manychat_pattern` | *"manychat auto-reply"* | 40 |

**Confidence score** = rule matches + keyword density bonus + optional spaCy boost (clamped 0–100)

---

## ⚖️ Legal & Ethical

| Constraint | How it's enforced |
|---|---|
| No auth bypass | Playwright opens public pages only — no login, cookies, or session injection |
| No automated actions | Read-only pipeline; zero writes to Instagram |
| Public data only | Equivalent to viewing a post in an incognito browser |
| No data retention | All scraped data is ephemeral per request — nothing stored |
| Rate limiting | One request per user action; no concurrent scraping |

> Users are responsible for complying with Instagram's Terms of Service  
> and applicable laws in their jurisdiction.

---

## 🛠 Extending

**Add a new detection rule** — edit `backend/nlp_detector.py`:
```python
(
    "my_pattern",
    re.compile(r"your regex", re.IGNORECASE),
    25,  # base score 0–40
),
```

**Add a new file type** — edit `backend/link_extractor.py`:
```python
".pptx": FileType.UNKNOWN,
```

**Swap to a transformer model** — replace `_spacy_boost()` in `nlp_detector.py` with any `sentence-transformers` call. The function returns `int` (bonus score) so the rest of the pipeline is untouched.

---

## 📄 License

MIT — see [LICENSE](LICENSE)
