export function ResourceCard({ type, children }) {
  const labels = {
    file:       "◈ RESOURCE FOUND",
    link:       "◉ LINKS EXTRACTED",
    automation: "◎ AUTOMATION INFERRED",
    none:       "○ RESULT",
  };
  return (
    <div className={`rc-box rc${(type || "n")[0]}`}>
      <div className="rc-lbl">{labels[type] || "RESULT"}</div>
      {children}
    </div>
  );
}
export default ResourceCard;
