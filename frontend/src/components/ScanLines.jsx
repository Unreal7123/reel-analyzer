/* ResourceCard.jsx */
export function ResourceCard({ type, children }) {
  const labels = {
    file: "◈ RESOURCE FOUND",
    link: "◉ LINKS EXTRACTED",
    automation: "◎ AUTOMATION INFERRED",
    none: "○ RESULT",
  };
  return (
    <div className={`resource-card resource-${type}`}>
      <div className="resource-label">{labels[type] || "RESULT"}</div>
      {children}
    </div>
  );
}
export default ResourceCard;


/* ─────────────────────────────────────────────────────────────────────────── */
/* ScanLines.jsx — CRT scanline overlay */
export function ScanLines() {
  return <div className="scanlines" aria-hidden="true" />;
}


/* ─────────────────────────────────────────────────────────────────────────── */
/* StatusBar.jsx — bottom status strip */
export function StatusBar({ loading, result }) {
  const status = loading
    ? "SCANNING TARGET…"
    : result
    ? `LAST SCAN: ${result.result_case?.replace(/_/g, " ").toUpperCase()} | ${result.processing_time_ms}ms`
    : "SYSTEM READY";

  return (
    <footer className="status-bar">
      <span className="status-indicator" data-active={loading} />
      <span className="status-text">{status}</span>
      <span className="status-right">
        REELSCAN v1.0 &nbsp;|&nbsp; PUBLIC DATA ONLY &nbsp;|&nbsp; NON-INTRUSIVE
      </span>
    </footer>
  );
}
