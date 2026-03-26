# 🔍 ReelScan — Instagram Automation Detector

> Detects ManyChat / DM-bot automation in public Instagram Reels. Analyzes captions, comment spam, emoji patterns & links.

[![Public Data Only](https://img.shields.io/badge/Data-Public%20Only-green)]()
[![Non-Intrusive](https://img.shields.io/badge/Approach-Non--Intrusive-blue)]()
[![OSINT Tool](https://img.shields.io/badge/Purpose-OSINT%20Research-orange)]()

---

## 🚀 What Is This?

ReelScan is an **agent-based** Instagram Reel analysis pipeline. Each module is a specialized agent with a clear mission, strict rules, and defined deliverables — inspired by the [agency-agents](https://github.com/msitarzewski/agency-agents) organizational pattern.

Paste an Instagram Reel URL and ReelScan will:
1. **Scrape** public page data (caption, comments, metadata)
2. **Clean** and normalize text (emojis, spam, invisible characters)
3. **Detect** automation patterns using rule-based NLP + spaCy
4. **Extract** and resolve resource links (PDFs, shortened URLs)
5. **Build** a confidence-scored analysis response with actionable insights

## 🎭 The Agent Roster

See **[AGENTS.md](AGENTS.md)** for the complete roster with pipeline flow diagram.

| Division | Agent | Role |
|----------|-------|------|
| 🕷️ Scraping | Instagram Extractor | Multi-strategy HTML data extraction |
| 🧹 Processing | Data Cleaner | Text normalization & deduplication |
| 🔍 Analysis | NLP Detector | 9+ rule pattern matching + spaCy |
| 🔗 Analysis | Link Extractor | URL resolution & file type detection |
| 🧠 Inference | Response Builder | Result assembly & action generation |
| 🖥️ Frontend | UI Developer | Dark terminal-aesthetic React dashboard |

## ⚡ Quick Start

### Local Development

```bash
# 1. Clone
git clone https://github.com/your-repo/instagram-reel-analyzer.git
cd instagram-reel-analyzer

# 2. Backend
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Docker

```bash
docker-compose up --build
# → Frontend: http://localhost:80
# → Backend:  http://localhost:8000
```

## 📁 Project Structure

```
instagram-reel-analyzer/
├── agents/                          # Agent definitions (agency-agents style)
│   ├── scraping/
│   │   └── scraping-instagram-extractor.md
│   ├── processing/
│   │   └── processing-data-cleaner.md
│   ├── analysis/
│   │   ├── analysis-nlp-detector.md
│   │   └── analysis-link-extractor.md
│   ├── inference/
│   │   └── inference-response-builder.md
│   └── frontend/
│       └── frontend-ui-developer.md
├── backend/
│   ├── agents/                      # Agent Python implementations
│   │   ├── scraper.py
│   │   ├── data_processor.py
│   │   ├── nlp_detector.py
│   │   ├── link_extractor.py
│   │   └── inference_engine.py
│   ├── models.py                    # Shared Pydantic models
│   ├── main.py                      # FastAPI orchestrator
│   └── requirements.txt
├── frontend/                        # React + Vite SPA
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── index.css
│   │   └── components/
│   └── package.json
├── AGENTS.md                        # Agent roster overview
├── README.md
├── render.yaml                      # Render deployment
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── nginx.conf
```

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/analyze` | Analyze an Instagram Reel URL |
| `GET` | `/demo/{case}` | Demo cases: `file`, `link`, `automation`, `none` |
| `GET` | `/health` | Health check |

### Example Request

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/reel/XXXXX/"}'
```

## 📊 Detection Capabilities

- **9+** NLP pattern rules with additive confidence scoring
- **23** automation emoji signatures tracked
- **4** HTML extraction strategies with fallback chain
- **10+** suggested action templates
- Spam rate analysis across comment populations
- Shortened URL resolution with redirect chain following

## ⚖️ Ethics & Disclaimer

- Analyzes **publicly accessible** data only
- No login bypass, no automated actions, no DM triggering
- For **OSINT & research use** only
- Respects Instagram's public page structure

## 📜 License

MIT
