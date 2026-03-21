// Resolves to "" in production (nginx proxies /api/*)
// and to "http://localhost:8000" in local dev (vite proxy)
const API = import.meta.env.VITE_API_URL ?? "";

export async function analyzeReel(url) {
  const res = await fetch(`${API}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return res.json();
}

export async function fetchDemo(caseId) {
  const res = await fetch(`${API}/demo/${caseId}`);
  if (!res.ok) throw new Error(`Demo fetch failed: ${res.status}`);
  return res.json();
}

export async function checkHealth() {
  const res = await fetch(`${API}/health`);
  return res.json();
}
