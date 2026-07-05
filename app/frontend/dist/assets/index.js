const { useState, useEffect, useRef, useCallback } = React;
const API = window.location.origin;

async function post(path, body) {
  const r = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.json();
}
async function get(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(r.status);
  return r.json();
}
async function uploadFile(path, file) {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`${API}${path}`, { method: "POST", body: form });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.json();
}

function md(text) {
  if (!text) return "";
  return text.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/\*\*(.*?)\*\*/g,"<strong class='text-white font-semibold'>$1</strong>")
    .replace(/\*(.*?)\*/g,"<em>$1</em>")
    .replace(/`(.*?)`/g,"<code class='bg-element-blue/10 px-1.5 py-0.5 rounded text-element-cyan text-[11px] font-mono'>$1</code>")
    .replace(/^### (.*$)/gm,"<h3 class='text-sm font-bold text-white mt-3 mb-1'>$1</h3>")
    .replace(/^## (.*$)/gm,"<h2 class='text-base font-bold text-white mt-4 mb-2'>$1</h2>")
    .replace(/^# (.*$)/gm,"<h1 class='text-lg font-bold text-white mt-4 mb-2'>$1</h1>")
    .replace(/^- (.*$)/gm,"<li class='ml-4 text-white/80 list-disc'>$1</li>")
    .replace(/^\d+\. (.*$)/gm,"<li class='ml-4 text-white/80 list-decimal'>$1</li>")
    .replace(/\n/g,"<br/>");
}

// ============================================================
// ICONS
// ============================================================
function IconDoc() { return <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>; }
function IconUpload() { return <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>; }
function IconChat() { return <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" /></svg>; }
function IconCompare() { return <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>; }
function IconDownload() { return <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>; }

// ============================================================
// STATUS BADGES
// ============================================================
function StatusBadge({ status }) {
  const map = {
    current: { bg: "bg-emerald-500/15", border: "border-emerald-500/30", text: "text-emerald-300" },
    superseded: { bg: "bg-amber-500/15", border: "border-amber-500/30", text: "text-amber-300" },
    unknown: { bg: "bg-slate-500/15", border: "border-slate-500/30", text: "text-slate-300" },
    completed: { bg: "bg-emerald-500/15", border: "border-emerald-500/30", text: "text-emerald-300" },
    processing: { bg: "bg-blue-500/15", border: "border-blue-500/30", text: "text-blue-300" },
    failed: { bg: "bg-red-500/15", border: "border-red-500/30", text: "text-red-300" },
  };
  const s = map[status] || map.unknown;
  return <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase ${s.bg} border ${s.border} ${s.text}`}>{status}</span>;
}

// ============================================================
// DOCUMENT LIBRARY
// ============================================================
function DocumentLibrary({ documents, onRefresh, loading }) {
  return (
    <div className="h-full flex flex-col">
      {/* Banner */}
      <div className="glass-banner rounded-2xl mx-6 mt-6 p-6 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Document Library</h2>
          <p className="text-sm text-white/50 mt-1">{documents.length} engineering specifications indexed and searchable</p>
        </div>
        <button onClick={onRefresh} disabled={loading} className="px-5 py-2.5 rounded-xl text-xs font-semibold glass border border-element-blue/30 text-element-cyan hover:bg-element-blue/10 transition-all disabled:opacity-50">
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-20 h-20 rounded-3xl glass flex items-center justify-center mb-5 pulse-glow"><IconDoc /></div>
            <h3 className="text-base font-semibold text-white/60">No documents yet</h3>
            <p className="text-sm text-white/30 mt-2">Upload PDF specifications to get started</p>
          </div>
        ) : (
          <div className="grid gap-3">
            {documents.map((doc, i) => (
              <div key={doc.document_id || i} className="glass-card rounded-xl p-5 fade-up" style={{ animationDelay: `${i * 50}ms` }}>
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h4 className="text-sm font-semibold text-white truncate">{doc.original_file_name}</h4>
                      <StatusBadge status={doc.status || doc.parsing_status || "unknown"} />
                    </div>
                    <div className="flex items-center gap-4 text-xs text-white/40">
                      {doc.spec_number && <span className="font-mono text-element-cyan font-medium">{doc.spec_number}</span>}
                      {doc.aedms_number && <span className="font-mono">{doc.aedms_number}</span>}
                      {doc.issue_year && <span>Year: {doc.issue_year}</span>}
                      {doc.page_count && <span>{doc.page_count} pages</span>}
                      {doc.title && <span className="truncate max-w-[250px] opacity-60">{doc.title}</span>}
                    </div>
                  </div>
                  <div className="text-right text-[10px] text-white/25 ml-4 shrink-0">
                    {doc.upload_timestamp && <div>{new Date(doc.upload_timestamp).toLocaleDateString()}</div>}
                    {doc.file_size_bytes && <div>{(doc.file_size_bytes / 1024).toFixed(0)} KB</div>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// PIPELINE STEP
// ============================================================
function PipelineStepRow({ step }) {
  const icons = {
    pending: <div className="w-6 h-6 rounded-full border border-white/15" />,
    running: <div className="w-6 h-6 rounded-full border-2 border-element-cyan/30 border-t-element-cyan spinner" />,
    completed: <div className="w-6 h-6 rounded-full bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center"><svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg></div>,
    failed: <div className="w-6 h-6 rounded-full bg-red-500/20 border border-red-500/50 flex items-center justify-center"><svg className="w-3.5 h-3.5 text-red-400" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/></svg></div>,
  };
  const bg = { pending: "bg-transparent", running: "bg-element-cyan/5", completed: "bg-emerald-500/5", failed: "bg-red-500/5" };
  return (
    <div className={`flex items-center gap-4 px-5 py-3.5 rounded-xl ${bg[step.status]} transition-all duration-300`}>
      {icons[step.status]}
      <div className="flex-1">
        <span className={`text-sm font-medium ${step.status === "running" ? "text-element-cyan" : step.status === "completed" ? "text-emerald-300" : step.status === "failed" ? "text-red-300" : "text-white/30"}`}>
          {step.label}
        </span>
        {step.detail && <p className={`text-xs mt-0.5 font-mono ${step.status === "failed" ? "text-red-300/60" : "text-white/25"}`}>{step.detail}</p>}
      </div>
      {step.duration_ms != null && <span className="text-xs text-white/25 font-mono">{(step.duration_ms / 1000).toFixed(1)}s</span>}
    </div>
  );
}

// ============================================================
// UPLOAD PAGE
// ============================================================
function UploadPage({ onUploadComplete }) {
  const [isDragging, setIsDragging] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [documentId, setDocumentId] = useState(null);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

  const stopPolling = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };

  const startPolling = (docId) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const r = await get(`/api/documents/${docId}/progress`);
        setProgress(r);
        if (r.status === "completed" || r.status === "failed") {
          stopPolling(); setProcessing(false); setDone(true);
          if (r.status === "completed" && onUploadComplete) onUploadComplete();
        }
      } catch (e) {}
    }, 1500);
  };

  useEffect(() => () => stopPolling(), []);

  const handleDrop = useCallback(async (e) => { e.preventDefault(); setIsDragging(false); const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith(".pdf")); if (files.length > 0) await processFile(files[0]); }, []);
  const handleFileSelect = async (e) => { const file = e.target.files[0]; if (file) await processFile(file); };

  const processFile = async (file) => {
    setProcessing(true); setError(null); setProgress(null); setDone(false); setDocumentId(null);
    try {
      const result = await uploadFile("/api/documents/upload", file);
      setDocumentId(result.document_id);
      startPolling(result.document_id);
    } catch (err) { setError(err.message); setProcessing(false); }
  };

  const reset = () => { setProcessing(false); setDocumentId(null); setProgress(null); setError(null); setDone(false); };

  return (
    <div className="h-full flex flex-col">
      <div className="glass-banner rounded-2xl mx-6 mt-6 p-6">
        <h2 className="text-xl font-bold text-white">Upload Document</h2>
        <p className="text-sm text-white/50 mt-1">Drag and drop PDF specifications — live pipeline progress tracking</p>
      </div>

      <div className="flex-1 p-6 overflow-y-auto">
        {!processing && !done && (
          <div className="flex flex-col items-center justify-center h-full">
            <div className={`drop-zone rounded-3xl p-16 text-center w-full max-w-xl cursor-pointer ${isDragging ? "active" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop} onClick={() => fileInputRef.current?.click()}>
              <div className="flex flex-col items-center gap-4">
                <div className="w-16 h-16 rounded-2xl glass flex items-center justify-center pulse-glow"><IconUpload /></div>
                <div className="text-base text-white/70 font-medium">Drop PDF here or click to browse</div>
                <div className="text-xs text-white/30">Supports engineering specifications up to 100MB</div>
              </div>
              <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={handleFileSelect} />
            </div>
            {error && <div className="mt-6 w-full max-w-xl p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-300 fade-up"><strong>Error:</strong> {error}</div>}
          </div>
        )}

        {(processing || done) && progress && (
          <div className="max-w-2xl mx-auto fade-up">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="text-base font-bold text-white">Pipeline Execution</h3>
                <p className="text-xs text-white/30 mt-1">ID: <span className="font-mono text-element-cyan">{documentId}</span></p>
              </div>
              <div className={`px-4 py-1.5 rounded-full text-xs font-bold ${progress.status === "completed" ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30" : progress.status === "failed" ? "bg-red-500/15 text-red-400 border border-red-500/30" : "bg-element-blue/15 text-element-cyan border border-element-blue/30"}`}>
                {progress.status === "completed" ? "COMPLETED" : progress.status === "failed" ? "FAILED" : "RUNNING"}
              </div>
            </div>
            <div className="w-full h-2 rounded-full bg-white/5 mb-6 overflow-hidden">
              <div className={`h-full rounded-full transition-all duration-700 ${progress.status === "completed" ? "bg-gradient-to-r from-emerald-500 to-emerald-400" : progress.status === "failed" ? "bg-red-500" : "bg-gradient-to-r from-element-blue to-element-cyan"}`} style={{ width: `${progress.percent}%` }} />
            </div>
            <div className="space-y-2 glass-card rounded-2xl p-3">
              {progress.steps.map((step, i) => <PipelineStepRow key={step.step_name} step={step} />)}
            </div>
            {done && <div className="mt-6 flex justify-center"><button onClick={reset} className="px-6 py-2.5 rounded-xl text-sm font-semibold glass border border-element-blue/30 text-element-cyan hover:bg-element-blue/10 transition-all">Upload Another</button></div>}
          </div>
        )}

        {processing && !progress && (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="w-14 h-14 border-2 border-element-cyan/30 border-t-element-cyan rounded-full spinner" />
            <p className="text-sm text-white/40 mt-4">Starting pipeline...</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// CHAT PAGE
// ============================================================
function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [citations, setCitations] = useState([]);
  const chatEndRef = useRef(null);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const sendMessage = async (text) => {
    const msg = text || input.trim();
    if (!msg) return;
    setInput("");
    const userMsg = { role: "user", content: msg };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true); setCitations([]);
    try {
      const history = messages.slice(-6).map(m => ({ role: m.role, content: m.content }));
      const result = await post("/api/chat", { message: msg, history });
      setMessages(prev => [...prev, { role: "assistant", content: result.answer }]);
      setCitations(result.citations || []);
    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: `Error: ${err.message}` }]);
    }
    setLoading(false);
  };

  const suggestions = [
    "What changed between the 2020 and 2026 S-400 specification?",
    "What are the requirements for certificate of conformance?",
    "Compare the testing requirements across versions",
    "What sections cover recertification procedures?",
    "List all quality management requirements",
    "What is the scope of S-SPEC-35?",
  ];

  return (
    <div className="h-full flex flex-col">
      <div className="glass-banner rounded-2xl mx-6 mt-6 p-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Specification Assistant</h2>
          <p className="text-sm text-white/50 mt-1">Ask questions about your uploaded documents • AI-powered analysis</p>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-white/30">
          <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
          <span>RAG Active</span>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden mx-6 mb-6 mt-4 gap-4">
        <div className="flex-1 flex flex-col glass-card rounded-2xl overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full">
                <div className="w-16 h-16 rounded-2xl glass flex items-center justify-center mb-5 pulse-glow"><IconChat /></div>
                <h3 className="text-base font-semibold text-white/60 mb-5">Ask about your specifications</h3>
                <div className="grid grid-cols-2 gap-2.5 max-w-lg">
                  {suggestions.map((s, i) => (
                    <button key={i} onClick={() => sendMessage(s)} className="px-4 py-3 rounded-xl glass border border-white/5 text-xs text-white/50 hover:text-white hover:border-element-blue/30 hover:bg-element-blue/5 transition-all text-left leading-relaxed">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} ${msg.role === "user" ? "slide-right" : "slide-left"}`}>
                {msg.role !== "user" && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center mr-3 bg-element-blue/10 border border-element-blue/20">
                    <IconChat />
                  </div>
                )}
                <div className={`max-w-[75%] rounded-2xl px-5 py-3.5 ${msg.role === "user" ? "bg-gradient-to-br from-element-blue to-element-blue-dark text-white shadow-glow rounded-br-sm" : "glass-strong text-white/90 rounded-bl-sm"}`}>
                  <div className="text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: md(msg.content) }} />
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex items-start slide-left">
                <div className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center mr-3 bg-element-blue/10 border border-element-blue/20"><IconChat /></div>
                <div className="glass-strong rounded-2xl px-5 py-3.5 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-element-cyan typing-dot" />
                  <div className="w-2 h-2 rounded-full bg-element-cyan typing-dot" />
                  <div className="w-2 h-2 rounded-full bg-element-cyan typing-dot" />
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="px-5 py-4 border-t border-white/5">
            <form onSubmit={(e) => { e.preventDefault(); sendMessage(); }} className="flex gap-3">
              <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about your engineering specifications..." className="flex-1 glass-input rounded-xl px-5 py-3.5 text-sm text-white placeholder-white/30" disabled={loading} />
              <button type="submit" disabled={!input.trim() || loading} className="px-6 py-3.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-element-blue to-element-blue-dark text-white hover:shadow-glow transition-all disabled:opacity-30">Send</button>
            </form>
          </div>
        </div>

        {citations.length > 0 && (
          <div className="w-72 glass-card rounded-2xl overflow-y-auto p-4">
            <h3 className="text-[10px] font-bold text-white/50 uppercase tracking-wider mb-3">Sources</h3>
            <div className="space-y-2">
              {citations.map((c, i) => (
                <div key={i} className="glass rounded-lg p-3 fade-up" style={{ animationDelay: `${i * 50}ms` }}>
                  <div className="text-[11px] font-medium text-white/70 truncate">{c.document_name}</div>
                  <div className="flex items-center gap-2 mt-1 text-[9px] text-white/40">
                    {c.issue_year && <span>Year: {c.issue_year}</span>}
                    {c.page_number && <span>P.{c.page_number}</span>}
                  </div>
                  {c.section_title && <div className="text-[9px] text-element-cyan/60 mt-1 truncate">{c.section_title}</div>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// COMPARE PAGE
// ============================================================
function ComparePage({ documents }) {
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const toggleDoc = (docId) => { setSelectedDocs(prev => prev.includes(docId) ? prev.filter(d => d !== docId) : [...prev, docId]); };

  const runCompare = async () => {
    if (selectedDocs.length < 2) return;
    setLoading(true); setResults(null);
    try { const result = await post("/api/compare", { document_ids: selectedDocs }); setResults(result); }
    catch (err) { setResults({ error: err.message }); }
    setLoading(false);
  };

  const downloadDocx = async () => {
    if (!results || !results.conclusion) return;
    setDownloading(true);
    try {
      const r = await fetch(`${API}/api/compare/download-docx`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ document_ids: selectedDocs, conclusion: results.conclusion }) });
      if (!r.ok) throw new Error("Download failed");
      const blob = await r.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url;
      a.download = r.headers.get("Content-Disposition")?.split("filename=")[1]?.replace(/"/g, "") || "Comparison_Report.docx";
      document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
    } catch (err) { alert("Failed to download: " + err.message); }
    setDownloading(false);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="glass-banner rounded-2xl mx-6 mt-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">Compare Versions</h2>
            <p className="text-sm text-white/50 mt-1">Select 2+ documents for AI-powered difference analysis</p>
          </div>
          <div className="flex gap-3">
            {results && results.conclusion && (
              <button onClick={downloadDocx} disabled={downloading} className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-emerald-600/80 hover:bg-emerald-500 text-white transition-all disabled:opacity-50 flex items-center gap-2">
                {downloading ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full spinner" /> : <IconDownload />}
                {downloading ? "Generating..." : "Download .docx"}
              </button>
            )}
            <button onClick={runCompare} disabled={selectedDocs.length < 2 || loading} className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-gradient-to-r from-element-blue to-element-blue-dark text-white hover:shadow-glow transition-all disabled:opacity-30 flex items-center gap-2">
              {loading && <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full spinner" />}
              {loading ? "Analyzing..." : `Compare (${selectedDocs.length})`}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mt-4">
          {documents.map(d => {
            const isSelected = selectedDocs.includes(d.document_id);
            return (
              <button key={d.document_id} onClick={() => toggleDoc(d.document_id)}
                className={`px-4 py-2 rounded-xl text-xs border transition-all ${isSelected ? "bg-element-blue/15 border-element-blue/40 text-element-cyan font-medium shadow-glow" : "glass border-white/8 text-white/50 hover:border-white/20 hover:text-white/70"}`}>
                {d.original_file_name} <span className="text-white/30">({d.issue_year || "?"})</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {!results && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl glass flex items-center justify-center mb-5 pulse-glow"><IconCompare /></div>
            <h3 className="text-base font-semibold text-white/60">Select 2+ documents above</h3>
            <p className="text-sm text-white/30 mt-2 max-w-sm">AI analyzes differences, assesses risk, and generates a downloadable report</p>
            <p className="text-xs text-white/15 mt-4">Tip: You can also ask in Chat — "Compare the 2020 and 2026 versions"</p>
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="w-14 h-14 border-2 border-element-cyan/30 border-t-element-cyan rounded-full spinner" />
            <p className="text-sm text-white/40 mt-4">AI is analyzing differences...</p>
            <p className="text-xs text-white/20 mt-1">This takes 15-20 seconds</p>
          </div>
        )}

        {results && results.error && (
          <div className="p-5 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-300">{results.error}</div>
        )}

        {results && results.conclusion && (
          <div className="max-w-4xl mx-auto fade-up">
            <div className="glass-card rounded-2xl p-6 border-l-4 border-element-blue">
              <h3 className="text-xs font-bold text-element-cyan uppercase tracking-wider mb-4 flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
                AI Comparison Analysis
              </h3>
              <div className="text-sm text-white/80 leading-relaxed" dangerouslySetInnerHTML={{ __html: md(results.conclusion) }} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// MAIN APP
// ============================================================
function App() {
  const [page, setPage] = useState("library");
  const [documents, setDocuments] = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);

  const loadDocuments = async () => {
    setDocsLoading(true);
    try { const result = await get("/api/documents"); setDocuments(result.documents || []); }
    catch (e) { console.error("Failed to load docs:", e); }
    setDocsLoading(false);
  };

  useEffect(() => { loadDocuments(); }, []);

  const NAV_ITEMS = [
    { id: "library", label: "Documents", icon: IconDoc },
    { id: "upload", label: "Upload", icon: IconUpload },
    { id: "chat", label: "Chat", icon: IconChat },
    { id: "compare", label: "Compare", icon: IconCompare },
  ];

  return (
    <div className="h-screen flex">
      {/* Sidebar */}
      <div className="w-60 glass-sidebar flex flex-col">
        {/* Logo + Brand */}
        <div className="p-5 border-b border-white/5">
          <div className="flex items-center gap-3">
            <img src="/images/element-logo.png" alt="Element" className="h-8" onError={(e) => { e.target.style.display = "none"; }} />
            <div>
              <div className="text-sm font-bold text-white">Spec Intelligence</div>
              <div className="text-[10px] text-element-cyan/60 font-medium">PLATFORM</div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1.5">
          {NAV_ITEMS.map(item => (
            <button key={item.id} onClick={() => setPage(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${page === item.id ? "nav-active text-white" : "text-white/40 hover:text-white/70 hover:bg-white/3"}`}>
              <item.icon />
              {item.label}
            </button>
          ))}
        </nav>

        {/* Stats Footer */}
        <div className="p-4 border-t border-white/5">
          <div className="glass rounded-xl p-3 space-y-2">
            <div className="flex justify-between text-[10px]"><span className="text-white/30">Documents</span><span className="text-white/60 font-medium">{documents.length}</span></div>
            <div className="flex justify-between text-[10px]"><span className="text-white/30">LLM Engine</span><span className="text-emerald-400 font-medium">Llama 3.3 70B</span></div>
            <div className="flex justify-between text-[10px]"><span className="text-white/30">Storage</span><span className="text-white/60 font-medium">Unity Catalog</span></div>
          </div>
          <div className="mt-3 flex items-center gap-2 justify-center">
            <img src="/images/databricks-logo.png" alt="Databricks" className="h-3.5 opacity-30" onError={(e) => { e.target.style.display = "none"; }} />
            <span className="text-[9px] text-white/20">Powered by Databricks</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden bg-mesh">
        {page === "library" && <DocumentLibrary documents={documents} onRefresh={loadDocuments} loading={docsLoading} />}
        {page === "upload" && <UploadPage onUploadComplete={loadDocuments} />}
        {page === "chat" && <ChatPage />}
        {page === "compare" && <ComparePage documents={documents} />}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
