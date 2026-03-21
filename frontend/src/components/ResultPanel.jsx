import ConfidenceBar from "./ConfidenceBar";
import ResourceCard from "./ResourceCard";

export default function ResultPanel({ result, loading, error, lastUrl }) {
  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!result) return <IdleState />;
  return <ResultDisplay result={result} />;
}

/* ─── Idle state ─────────────────────────────────────────────────────────── */
function IdleState() {
  return (
    <div className="result-card result-idle">
      <div className="card-label">ANALYSIS OUTPUT</div>
      <div className="idle-content">
        <div className="idle-grid">
          {Array.from({ length: 64 }).map((_, i) => (
            <span key={i} className="idle-cell">
              {Math.random() > 0.85 ? "1" : "0"}
            </span>
          ))}
        </div>
        <p className="idle-msg">AWAITING TARGET URL</p>
        <p className="idle-sub">Submit an Instagram Reel URL to begin analysis</p>
      </div>
    </div>
  );
}

/* ─── Loading state ───────────────────────────────────────────────────────── */
function LoadingState() {
  const steps = [
    "Launching Playwright browser…",
    "Navigating to Instagram Reel…",
    "Extracting caption & comments…",
    "Running NLP detection…",
    "Resolving resource links…",
    "Building inference model…",
  ];
  return (
    <div className="result-card result-loading">
      <div className="card-label">SCANNING</div>
      <div className="loading-content">
        <div className="loading-radar">
          <div className="radar-ring r1" />
          <div className="radar-ring r2" />
          <div className="radar-ring r3" />
          <div className="radar-dot" />
          <div className="radar-sweep" />
        </div>
        <div className="loading-steps">
          {steps.map((s, i) => (
            <div key={i} className="loading-step" style={{ animationDelay: `${i * 0.4}s` }}>
              <span className="step-arrow">›</span> {s}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── Error state ─────────────────────────────────────────────────────────── */
function ErrorState({ message }) {
  return (
    <div className="result-card result-error">
      <div className="card-label">ERROR</div>
      <div className="error-content">
        <div className="error-icon">✕</div>
        <p className="error-title">ANALYSIS FAILED</p>
        <p className="error-msg">{message}</p>
        <p className="error-hint">
          Check the URL format and ensure the backend is running on port 8000.
        </p>
      </div>
    </div>
  );
}

/* ─── Main result display ─────────────────────────────────────────────────── */
function ResultDisplay({ result }) {
  const {
    result_case,
    automation_detected,
    trigger_keywords,
    confidence_score,
    matched_patterns,
    file_type,
    download_link,
    extracted_links,
    suggested_action,
    analysis_summary,
    processing_time_ms,
    post_url,
  } = result;

  const caseConfig = {
    file_found:          { color: "green",  icon: "◈", label: "FILE DETECTED" },
    link_found:          { color: "blue",   icon: "◉", label: "LINK EXTRACTED" },
    automation_detected: { color: "amber",  icon: "◎", label: "BOT PATTERN FOUND" },
    no_automation:       { color: "dim",    icon: "○", label: "NO PATTERN DETECTED" },
  };

  const cfg = caseConfig[result_case] || caseConfig.no_automation;

  return (
    <div className={`result-card result-active result-${cfg.color}`}>
      <div className="card-label">ANALYSIS OUTPUT</div>

      {/* ── Case header ── */}
      <div className={`case-header case-${cfg.color}`}>
        <span className="case-icon">{cfg.icon}</span>
        <span className="case-label">{cfg.label}</span>
        <span className="case-time">{processing_time_ms}ms</span>
      </div>

      {/* ── Confidence ── */}
      <ConfidenceBar score={confidence_score} />

      {/* ── Case 1: File Found ── */}
      {result_case === "file_found" && (
        <ResourceCard type="file">
          <div className="resource-row">
            <span className="resource-icon file-icon">
              {file_type === "pdf" ? "📄" : "📦"}
            </span>
            <div>
              <p className="resource-title">
                {file_type?.toUpperCase()} FILE DETECTED
              </p>
              <p className="resource-url">{download_link}</p>
            </div>
          </div>
          <div className="action-buttons">
            <a href={download_link} download className="btn-action btn-green">
              ↓ DOWNLOAD {file_type?.toUpperCase()}
            </a>
            <a href={download_link} target="_blank" rel="noopener noreferrer"
               className="btn-action btn-outline">
              ↗ PREVIEW
            </a>
          </div>
        </ResourceCard>
      )}

      {/* ── Case 2: Link Found ── */}
      {result_case === "link_found" && (
        <ResourceCard type="link">
          {extracted_links.map((link, i) => (
            <div key={i} className="link-row">
              <span className="link-index">{String(i + 1).padStart(2, "0")}</span>
              <span className="link-url">{link}</span>
              <div className="link-actions">
                <button
                  className="btn-icon"
                  title="Copy"
                  onClick={() => navigator.clipboard.writeText(link)}
                >
                  ⎘
                </button>
                <a href={link} target="_blank" rel="noopener noreferrer"
                   className="btn-icon" title="Open">
                  ↗
                </a>
              </div>
            </div>
          ))}
        </ResourceCard>
      )}

      {/* ── Case 3: Automation w/o link ── */}
      {result_case === "automation_detected" && (
        <ResourceCard type="automation">
          <div className="suggestion-box">
            <div className="suggestion-header">
              <span className="pulse-dot" /> INFERRED AUTOMATION FLOW
            </div>
            <p className="suggestion-text">{suggested_action}</p>
          </div>
          <div className="keywords-section">
            <span className="section-label">TRIGGER KEYWORDS</span>
            <div className="keyword-chips">
              {trigger_keywords.map((kw) => (
                <span key={kw} className="keyword-chip">{kw}</span>
              ))}
            </div>
          </div>
        </ResourceCard>
      )}

      {/* ── Case 4: No automation ── */}
      {result_case === "no_automation" && (
        <ResourceCard type="none">
          <div className="no-result">
            <span className="no-result-icon">—</span>
            <p>No automation or resource detected in this post.</p>
          </div>
        </ResourceCard>
      )}

      {/* ── Matched patterns ── */}
      {matched_patterns?.length > 0 && (
        <div className="patterns-section">
          <span className="section-label">MATCHED RULES</span>
          <div className="patterns-list">
            {matched_patterns.map((p) => (
              <span key={p} className="pattern-tag">{p.replace(/_/g, " ")}</span>
            ))}
          </div>
        </div>
      )}

      {/* ── Summary ── */}
      <div className="summary-section">
        <span className="section-label">ANALYSIS SUMMARY</span>
        <p className="summary-text">{analysis_summary}</p>
      </div>

      {/* ── Target URL ── */}
      <div className="target-url">
        <span className="section-label">TARGET</span>
        <span className="target-text">{post_url}</span>
      </div>
    </div>
  );
}
