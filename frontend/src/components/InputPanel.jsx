import { useState } from "react";

const DEMOS = [
  { id:"file",       label:"PDF Found",    cls:"bdg" },
  { id:"link",       label:"Link Found",   cls:"bdb" },
  { id:"automation", label:"Bot Detected", cls:"bda" },
  { id:"none",       label:"No Pattern",   cls:"bdd" },
];

export default function InputPanel({ onAnalyze, onDemo, loading }) {
  const [url, setUrl]   = useState("");
  const [err, setErr]   = useState("");

  const validate = v => {
    if (!v.trim()) return "URL is required";
    if (!v.includes("instagram.com/reel/") && !v.includes("instagram.com/p/") && !v.includes("instagr.am/"))
      return "Must be an Instagram Reel URL (instagram.com/reel/…)";
    return "";
  };

  const submit = e => {
    e.preventDefault();
    const e2 = validate(url);
    if (e2) { setErr(e2); return; }
    setErr("");
    onAnalyze(url.trim());
  };

  return (
    <div className="card">
      <div className="clabel">TARGET INPUT</div>

      <form onSubmit={submit} className="input-form">
        <div className="input-wrap">
          <span className="input-pfx">URL://</span>
          <input
            className="url-input"
            type="text"
            placeholder="instagram.com/reel/XXXXX/"
            value={url}
            onChange={e => { setUrl(e.target.value); if(err) setErr(""); }}
            spellCheck={false}
            autoComplete="off"
          />
        </div>
        {err && <p className="verr">⚠ {err}</p>}
        <button type="submit" className="btn-analyze" disabled={loading}>
          {loading
            ? <span className="btn-loading"><span className="spin"/>SCANNING…</span>
            : "▶  ANALYZE REEL"}
        </button>
      </form>

      <div className="demo-sec">
        <div className="demo-lbl">DEMO CASES →</div>
        <div className="demo-row">
          {DEMOS.map(d => (
            <button key={d.id} className={`bdemo ${d.cls}`}
              onClick={() => onDemo(d.id)} disabled={loading}>
              {d.label}
            </button>
          ))}
        </div>
      </div>

      <div className="disc">
        <span style={{ fontSize:14, flexShrink:0 }}>⚖</span>
        <span>
          Analyzes <strong>publicly accessible</strong> data only.
          No login bypass, no automated actions, no DM triggering.
          For OSINT &amp; research use.
        </span>
      </div>
    </div>
  );
}
