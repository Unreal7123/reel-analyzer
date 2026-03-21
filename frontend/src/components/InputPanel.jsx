import { useState } from "react";

const DEMO_CASES = [
  { id: "file", label: "PDF Found", color: "green" },
  { id: "link", label: "Link Found", color: "blue" },
  { id: "automation", label: "Bot Detected", color: "amber" },
  { id: "none", label: "No Pattern", color: "dim" },
];

export default function InputPanel({ onAnalyze, onDemo, loading }) {
  const [url, setUrl] = useState("");
  const [validationError, setValidationError] = useState("");

  const validate = (val) => {
    if (!val.trim()) return "URL is required";
    if (
      !val.includes("instagram.com/reel/") &&
      !val.includes("instagram.com/p/") &&
      !val.includes("instagr.am/")
    ) {
      return "Must be an Instagram Reel URL";
    }
    return "";
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const err = validate(url);
    if (err) {
      setValidationError(err);
      return;
    }
    setValidationError("");
    onAnalyze(url.trim());
  };

  return (
    <div className="input-card">
      <div className="card-label">TARGET INPUT</div>

      <form onSubmit={handleSubmit} className="input-form">
        <div className="input-wrapper">
          <span className="input-prefix">URL://</span>
          <input
            type="text"
            className={`reel-input ${validationError ? "input-error" : ""}`}
            placeholder="instagram.com/reel/XXXXX/"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              if (validationError) setValidationError("");
            }}
            spellCheck={false}
            autoComplete="off"
          />
        </div>
        {validationError && (
          <p className="validation-msg">⚠ {validationError}</p>
        )}
        <button
          type="submit"
          className="btn-analyze"
          disabled={loading}
        >
          {loading ? (
            <span className="btn-loading">
              <span className="spinner" /> SCANNING…
            </span>
          ) : (
            "▶ ANALYZE REEL"
          )}
        </button>
      </form>

      {/* Demo row */}
      <div className="demo-section">
        <span className="demo-label">DEMO CASES →</span>
        <div className="demo-buttons">
          {DEMO_CASES.map((d) => (
            <button
              key={d.id}
              className={`btn-demo btn-demo-${d.color}`}
              onClick={() => onDemo(d.id)}
              disabled={loading}
            >
              {d.label}
            </button>
          ))}
        </div>
      </div>

      {/* Legal disclaimer */}
      <div className="disclaimer">
        <span className="disclaimer-icon">⚖</span>
        <p>
          Analyzes <strong>publicly accessible</strong> data only. No login
          bypass, no automated actions, no DM triggering. For research &amp;
          educational use.
        </p>
      </div>
    </div>
  );
}
