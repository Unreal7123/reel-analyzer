import { useState, useEffect, useRef } from "react";
import InputPanel from "./components/InputPanel";
import ResultPanel from "./components/ResultPanel";
import { analyzeReel, fetchDemo } from "./api";

const STEPS = [
  { id:"01", label:"URL Validation"   },
  { id:"02", label:"Playwright Scraper"},
  { id:"03", label:"Data Processor"   },
  { id:"04", label:"NLP Detector"     },
  { id:"05", label:"Link Extractor"   },
  { id:"06", label:"Inference Engine" },
];

export default function App() {
  const [result,  setResult]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [step,    setStep]    = useState(-1);
  const canvasRef = useRef(null);

  // ── Particle background
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let raf;
    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    resize();
    window.addEventListener("resize", resize);

    const particles = Array.from({ length: 60 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: -Math.random() * 0.4 - 0.1,
      r: Math.random() * 1.5 + 0.3,
      alpha: Math.random() * 0.5 + 0.1,
      color: ["#00e5a0","#38bdf8","#a78bfa"][Math.floor(Math.random()*3)],
    }));

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        ctx.save();
        ctx.globalAlpha = p.alpha;
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        p.x += p.vx; p.y += p.vy;
        if (p.y < -5) { p.y = canvas.height + 5; p.x = Math.random() * canvas.width; }
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
      });
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);

  // ── Simulate step progress during loading
  useEffect(() => {
    if (!loading) { setStep(-1); return; }
    setStep(0);
    const timings = [0, 800, 1800, 3000, 4200, 5400];
    const timers = timings.map((t, i) => setTimeout(() => setStep(i), t));
    return () => timers.forEach(clearTimeout);
  }, [loading]);

  const run = async (fn) => {
    setLoading(true); setError(null); setResult(null);
    try { setResult(await fn()); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleAnalyze = (url) => run(() => analyzeReel(url));
  const handleDemo    = (c)   => run(() => fetchDemo(c));

  const statusText = loading
    ? `SCANNING · STEP ${step + 1}/6 — ${STEPS[step]?.label ?? "INIT"}…`
    : result
    ? `LAST SCAN: ${result.result_case?.replace(/_/g," ").toUpperCase()} | ${result.processing_time_ms}ms | ${result.confidence_score}% CONFIDENCE`
    : "SYSTEM READY — AWAITING TARGET";

  return (
    <>
      <canvas ref={canvasRef} id="particles-canvas" />

      <div className="app-wrap">
        {/* Header */}
        <header className="app-header">
          <div className="logo-row">
            <div className="logo-icon">🔍</div>
            <div>
              <div className="logo-text">ReelScan</div>
              <div className="logo-version">v1.0 · AUTOMATION DETECTOR</div>
            </div>
          </div>
          <p className="header-sub">
            Detects ManyChat / DM-bot automation in public Instagram Reels.
            Analyzes captions, comment spam, emoji patterns &amp; links.
          </p>
          <div className="header-badges">
            <span className="hbadge hbg">PUBLIC DATA ONLY</span>
            <span className="hbadge hba">NON-INTRUSIVE</span>
            <span className="hbadge hbb">OSINT RESEARCH TOOL</span>
          </div>
        </header>

        {/* Main grid */}
        <main className="main-grid">
          <div className="col-left">
            <InputPanel onAnalyze={handleAnalyze} onDemo={handleDemo} loading={loading} />
            <PipelineCard step={step} loading={loading} />
          </div>
          <div className="col-right">
            <ResultPanel result={result} loading={loading} error={error} step={step} />
          </div>
        </main>
      </div>

      {/* Status bar */}
      <footer className="sbar">
        <span className={`sind ${loading ? "active" : ""}`} />
        <span className="stx">{statusText}</span>
        <span className="srv">ReelScan v1.0 · Public Data Only · Non-Intrusive</span>
      </footer>
    </>
  );
}

function PipelineCard({ step, loading }) {
  return (
    <div className="card">
      <div className="clabel">PIPELINE</div>
      <div className="pip-steps">
        {STEPS.map((s, i) => {
          const isDone   = step > i;
          const isActive = step === i && loading;
          return (
            <div
              key={s.id}
              className={`pip-step ${isDone ? "pip-done" : ""}`}
            >
              <div className={`pip-node ${isActive ? "active" : ""} ${isDone ? "pip-done" : ""}`}>
                <span className="pip-id">{isDone ? "✓" : s.id}</span>
              </div>
              <span className="pip-lbl">{s.label}</span>
              <span className="pip-status">
                {isDone ? "DONE" : isActive ? "RUNNING" : ""}
              </span>
              {i < STEPS.length - 1 && <div className="pip-conn" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
