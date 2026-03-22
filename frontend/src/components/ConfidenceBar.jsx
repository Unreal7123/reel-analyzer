export default function ConfidenceBar({ score, color }) {
  return (
    <div className="conf-sec">
      <div className="conf-hdr">
        <span className="sec-l" style={{ margin:0 }}>CONFIDENCE SCORE</span>
        <span className="conf-val" style={{ color }}>{score}%</span>
      </div>
      <div className="conf-track">
        <div className="conf-fill" style={{ width:`${score}%`, background:color }} />
      </div>
      <div className="conf-sc"><span>LOW</span><span>MEDIUM</span><span>HIGH</span></div>
    </div>
  );
}
