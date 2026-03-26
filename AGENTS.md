# 🎭 ReelScan Agent Roster

A specialized team of agents powering the Instagram Reel automation detection pipeline. Each agent has a clear mission, strict rules, and defined deliverables.

---

## 🕷️ Scraping Division

| Agent | Description |
|-------|-------------|
| [Instagram Extractor](agents/scraping/scraping-instagram-extractor.md) | Multi-strategy public data extractor. Fetches HTML, parses JSON-LD, _sharedData, and relay blobs. |

## 🧹 Processing Division

| Agent | Description |
|-------|-------------|
| [Data Cleaner](agents/processing/processing-data-cleaner.md) | Text normalizer — removes emojis, invisible chars, spam, and rebuilds clean corpora. |

## 🔍 Analysis Division

| Agent | Description |
|-------|-------------|
| [NLP Detector](agents/analysis/analysis-nlp-detector.md) | Rule-based + spaCy automation pattern detector. Scores content against 9+ trigger patterns. |
| [Link Extractor](agents/analysis/analysis-link-extractor.md) | URL detective — finds, resolves, and classifies every link in Instagram content. |

## 🧠 Inference Division

| Agent | Description |
|-------|-------------|
| [Response Builder](agents/inference/inference-response-builder.md) | Final assembler — resolves result cases, generates actions, builds summaries. |

## 🖥️ Frontend Division

| Agent | Description |
|-------|-------------|
| [UI Developer](agents/frontend/frontend-ui-developer.md) | React/Vite specialist — dark terminal aesthetic, pipeline visualization, responsive panels. |

---

## 🔄 Pipeline Flow

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────────┐    ┌─────────────────┐
│  Instagram   │───▶│    Data      │───▶│     NLP      │───▶│     Link       │───▶│    Response      │
│  Extractor   │    │   Cleaner    │    │   Detector   │    │   Extractor    │    │    Builder       │
│   🕷️         │    │    🧹        │    │    🔍        │    │     🔗         │    │     🧠           │
└─────────────┘    └──────────────┘    └──────────────┘    └────────────────┘    └─────────────────┘
     ▲                                                                                    │
     │                        ┌──────────────┐                                            ▼
     └────────────────────────│  UI Developer │◀───────────────────────────────────── API Response
                              │     🖥️        │
                              └──────────────┘
```

## 📊 Stats
- **6** specialized agents across **5** divisions
- **9+** NLP detection rules with additive scoring
- **4** HTML extraction strategies with automatic fallback
- **23** automation emoji signatures tracked
- **10+** suggested action templates
