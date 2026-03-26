import ConfidenceBar    from "./ConfidenceBar";

export default function ResultPanel({ result, loading, error, step }) {
  if (loading) return <LoadingPanel step={step} />;
  if (error)   return <ErrorPanel msg={error} />;
  if (!result) return <IdlePanel />;
  return <ResultDisplay r={result} />;
}

/* ── Idle ────────────────────────────────────────────────────────── */
function IdlePanel() {
  return (
    <div className="rcard">
      <div className="clabel">ANALYSIS OUTPUT</div>
      <div className="idle-wrap">
        <div className="idle-orb" />
        <p className="idle-txt">AWAITING TARGET URL</p>
        <p className="idle-sub">Submit an Instagram Reel URL or load a demo case</p>
      </div>
    </div>
  );
}

/* ── Loading ──────────────────────────────────────────────────────── */
const LSTEPS = [
  "Launching Playwright browser…",
  "Navigating to Instagram Reel…",
  "Extracting caption & comments…",
  "Running NLP + spam analysis…",
  "Resolving resource links…",
  "Building inference model…",
];
function LoadingPanel({ step }) {
  return (
    <div className="rcard">
      <div className="clabel">SCANNING</div>
      <div className="load-wrap">
        <div className="radar-wrap">
          <div className="r-ring rr1"/><div className="r-ring rr2"/><div className="r-ring rr3"/>
          <div className="r-dot"/>
          <div className="r-sweep"/>
        </div>
        <div className="load-steps">
          {LSTEPS.map((s, i) => (
            <div
              key={i}
              className={`load-step ${i < step ? "done" : ""}`}
              style={{ animationDelay: `${i * 0.35}s` }}
            >
              <span className="step-dot" />
              {i < step ? "✓ " : i === step ? "▶ " : "  "}{s}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Error ────────────────────────────────────────────────────────── */
function ErrorPanel({ msg }) {
  return (
    <div className="rcard">
      <div className="clabel">ERROR</div>
      <div className="err-wrap">
        <div className="err-ic">✕</div>
        <p className="err-t">ANALYSIS FAILED</p>
        <p className="err-m">{msg}</p>
        <p className="err-m" style={{ fontSize: "11px", marginTop: 8, color: "var(--text3)" }}>
          Ensure the backend is running and the URL is a public Instagram Reel.
        </p>
      </div>
    </div>
  );
}

/* ── Main result ──────────────────────────────────────────────────── */
function ResultDisplay({ r }) {
  const CFG = {
    file_found:          { cls:"chg rg", icon:"◈", label:"FILE DETECTED"       },
    link_found:          { cls:"chb rb", icon:"◉", label:"LINK EXTRACTED"      },
    automation_detected: { cls:"cha ra", icon:"◎", label:"BOT PATTERN FOUND"   },
    no_automation:       { cls:"chd",   icon:"○", label:"NO PATTERN DETECTED" },
  };
  const cfg = CFG[r.result_case] || CFG.no_automation;
  const [cardCls, hdrCls] = cfg.cls.split(" ");
  const scoreColor =
    r.confidence_score >= 70 ? "var(--green)" :
    r.confidence_score >= 40 ? "var(--amber)" : "var(--text3)";

  return (
    <div className={`rcard ${cardCls || ""}`}>
      <div className="clabel">ANALYSIS OUTPUT</div>

      {/* Case header */}
      <div className={`case-hdr ${hdrCls || cardCls}`}>
        <span className="case-ico">{cfg.icon}</span>
        <span className="case-lbl">{cfg.label}</span>
        <span className="case-ms">{r.processing_time_ms}ms</span>
      </div>

      {/* Confidence */}
      <ConfidenceBar score={r.confidence_score} color={scoreColor} />

      {/* Case 1 — File */}
      {r.result_case === "file_found" && (
        <div className="rc-box rcg">
          <div className="rc-lbl">◈ RESOURCE FOUND</div>
          <div className="file-row">
            <span className="file-ic">📄</span>
            <div>
              <p className="file-tit">{(r.file_type || "FILE").toUpperCase()} DETECTED</p>
              <p className="file-url">{r.download_link}</p>
            </div>
          </div>
          <div className="action-row">
            <a href={r.download_link} download className="abt abt-green">↓ DOWNLOAD {(r.file_type||"").toUpperCase()}</a>
            <a href={r.download_link} target="_blank" rel="noopener noreferrer" className="abt abt-out">↗ PREVIEW</a>
          </div>
        </div>
      )}

      {/* Case 2 — Link */}
      {r.result_case === "link_found" && (
        <div className="rc-box rcb">
          <div className="rc-lbl">◉ LINKS EXTRACTED</div>
          {r.extracted_links.map((link, i) => (
            <div key={i} className="link-row">
              <span className="link-num">{String(i+1).padStart(2,"0")}</span>
              <span className="link-url">{link}</span>
              <div className="link-btns">
                <button className="lbtn" title="Copy" onClick={() => navigator.clipboard.writeText(link)}>⎘</button>
                <a href={link} target="_blank" rel="noopener noreferrer" className="lbtn" title="Open">↗</a>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Case 3 — Automation inferred */}
      {r.result_case === "automation_detected" && (
        <div className="rc-box rca">
          <div className="rc-lbl">◎ AUTOMATION INFERRED</div>
          <div className="sug-box">
            <div className="sug-hdr"><span className="pdot"/>INFERRED AUTOMATION FLOW</div>
            <p className="sug-txt">{r.suggested_action}</p>
          </div>
          {r.trigger_keywords?.length > 0 && (
            <>
              <span className="sec-l">TRIGGER KEYWORDS</span>
              <div className="kw-row">
                {r.trigger_keywords.map(k => (
                  <span key={k} className="kw-chip">{k}</span>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Case 4 — No automation */}
      {r.result_case === "no_automation" && (
        <div className="rc-box">
          <div className="no-res">
            <span className="no-res-ic">○</span>
            <p>No automation or resource detected in this post.</p>
          </div>
        </div>
      )}

      {/* Spam / Comment Analysis */}
      {r.spam_analysis?.total_comments > 0 && (
        <SpamSection spam={r.spam_analysis} />
      )}

      {/* Spam signals */}
      {r.spam_signals?.length > 0 && (
        <div className="signals-sec">
          <span className="sec-l">SPAM SIGNALS DETECTED</span>
          <div>
            {r.spam_signals.map((s, i) => (
              <span key={i} className="signal-tag" style={{ animationDelay: `${i*0.08}s` }}>⚡ {s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Matched rules */}
      {r.matched_patterns?.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <span className="sec-l">MATCHED RULES</span>
          <div className="ptags">
            {r.matched_patterns.map(p => (
              <span key={p} className="ptag">{p.replace(/_/g," ")}</span>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      <div className="summ-box">
        <span className="sec-l">ANALYSIS SUMMARY</span>
        {r.analysis_summary}
      </div>

      {/* Target URL */}
      <div className="target-row">
        <span className="sec-l" style={{ margin: 0 }}>TARGET</span>
        <span style={{ color:"var(--text2)", fontFamily:"var(--mono)", fontSize:11 }}>{r.post_url}</span>
      </div>
    </div>
  );
}

/* ── Spam Analysis Widget ─────────────────────────────────────────── */
function SpamSection({ spam }) {
  const maxEmoji = spam.top_emojis?.[0]?.count || 1;
  const scoreColor =
    spam.spam_score >= 60 ? "var(--red)" :
    spam.spam_score >= 30 ? "var(--amber)" : "var(--green)";

  return (
    <div className="spam-sec">
      <div className="rc-lbl">💬 COMMENT SPAM ANALYSIS</div>

      <div className="spam-score-row">
        <span className="spam-score-lbl">
          Spam Rate — {spam.total_comments} comments analyzed
        </span>
        <span className="spam-score-val" style={{ color: scoreColor }}>
          {spam.spam_score}%
        </span>
      </div>

      <div className="spam-grid">
        {/* Top repeated comments */}
        <div>
          <div className="spam-col-hdr">TOP REPEATED COMMENTS</div>
          {spam.top_comments?.slice(0, 5).map((c, i) => (
            <div key={i} className="spam-item">
              <span className="spam-text">{`"${c.text}"`}</span>
              <span className="spam-cnt">×{c.count}</span>
            </div>
          ))}
          {!spam.top_comments?.length && (
            <div style={{ color:"var(--text3)", fontSize:11 }}>No repeated comments</div>
          )}
        </div>

        {/* Top emojis */}
        <div>
          <div className="spam-col-hdr">TOP EMOJIS</div>
          {spam.top_emojis?.slice(0, 5).map((e, i) => (
            <div key={i} className="emoji-item">
              <span className="emoji-char">{e.emoji}</span>
              <div className="emoji-bar-wrap">
                <div className="emoji-bar" style={{ width: `${(e.count/maxEmoji)*100}%` }} />
              </div>
              <span className="emoji-cnt">×{e.count}</span>
            </div>
          ))}
          {!spam.top_emojis?.length && (
            <div style={{ color:"var(--text3)", fontSize:11 }}>No emojis found</div>
          )}
        </div>
      </div>
    </div>
  );
}
