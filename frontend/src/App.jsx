import { useState } from "react";
import InputPanel from "./components/InputPanel";
import ResultPanel from "./components/ResultPanel";
import { ScanLines, StatusBar } from "./components/ScanLines";
import { analyzeReel, fetchDemo } from "./api";

export default function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUrl, setLastUrl] = useState("");

  const handleAnalyze = async (url) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setLastUrl(url);
    try {
      setResult(await analyzeReel(url));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async (demoCase) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setLastUrl(`demo:${demoCase}`);
    try {
      setResult(await fetchDemo(demoCase));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-root">
      <ScanLines />
      <div className="app-layout">
        {/* ── Header ── */}
        <header className="app-header">
          <div className="header-logo">
            <span className="logo-bracket">[</span>
            <span className="logo-text">REEL<span className="logo-accent">SCAN</span></span>
            <span className="logo-bracket">]</span>
          </div>
          <p className="header-sub">
            Instagram Reel Automation Pattern Detector &amp; Resource Extractor
          </p>
          <div className="header-badges">
            <span className="badge badge-green">PUBLIC DATA ONLY</span>
            <span className="badge badge-amber">NON-INTRUSIVE</span>
            <span className="badge badge-blue">OSINT TOOL</span>
          </div>
        </header>

        {/* ── Main grid ── */}
        <main className="main-grid">
          <div className="col-left">
            <InputPanel
              onAnalyze={handleAnalyze}
              onDemo={handleDemo}
              loading={loading}
            />
            <PipelineDiagram />
          </div>
          <div className="col-right">
            <ResultPanel
              result={result}
              loading={loading}
              error={error}
              lastUrl={lastUrl}
            />
          </div>
        </main>

        <StatusBar loading={loading} result={result} />
      </div>
    </div>
  );
}

function PipelineDiagram() {
  const steps = [
    { id: "01", label: "URL Validation", icon: "⬡" },
    { id: "02", label: "Playwright Scraper", icon: "⬡" },
    { id: "03", label: "Data Processor", icon: "⬡" },
    { id: "04", label: "NLP Detector", icon: "⬡" },
    { id: "05", label: "Link Extractor", icon: "⬡" },
    { id: "06", label: "Inference Engine", icon: "⬡" },
  ];

  return (
    <div className="pipeline-card">
      <div className="card-label">PIPELINE</div>
      <div className="pipeline-steps">
        {steps.map((s, i) => (
          <div key={s.id} className="pipeline-step">
            <div className="step-node">
              <span className="step-id">{s.id}</span>
            </div>
            <span className="step-label">{s.label}</span>
            {i < steps.length - 1 && <div className="step-connector" />}
          </div>
        ))}
      </div>
    </div>
  );
}
