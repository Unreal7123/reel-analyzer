/* ConfidenceBar.jsx */
export default function ConfidenceBar({ score }) {
  const color =
    score >= 70 ? "var(--green)" :
    score >= 40 ? "var(--amber)" :
    "var(--dim)";

  return (
    <div className="confidence-section">
      <div className="confidence-header">
        <span className="section-label">CONFIDENCE SCORE</span>
        <span className="confidence-value" style={{ color }}>{score}%</span>
      </div>
      <div className="confidence-track">
        <div
          className="confidence-fill"
          style={{ width: `${score}%`, background: color }}
        />
        <div className="confidence-glow" style={{ left: `${score}%`, background: color }} />
      </div>
      <div className="confidence-scale">
        <span>LOW</span><span>MED</span><span>HIGH</span>
      </div>
    </div>
  );
}
