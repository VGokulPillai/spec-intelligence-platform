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
    .replace(/\*\*(.*?)\*\*/g,"<strong class='text-white'>$1</strong>")
    .replace(/\*(.*?)\*/g,"<em>$1</em>")
    .replace(/`(.*?)`/g,"<code class='bg-white/10 px-1 rounded text-element-cyan text-[11px]'>$1</code>")
    .replace(/^### (.*$)/gm,"<h3 class='text-sm font-bold text-white mt-2 mb-1'>$1</h3>")
    .replace(/^## (.*$)/gm,"<h2 class='text-base font-bold text-white mt-3 mb-1'>$1</h2>")
    .replace(/^# (.*$)/gm,"<h1 class='text-lg font-bold text-white mt-4 mb-2'>$1</h1>")
    .replace(/^- (.*$)/gm,"<li class='ml-3 text-white/80 list-disc'>$1</li>")
    .replace(/^\d+\. (.*$)/gm,"<li class='ml-3 text-white/80 list-decimal'>$1</li>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,"<a href='$2' class='text-element-cyan hover:underline'>$1</a>")
    .replace(/\n/g,"<br/>");
}

// ============================================================
// ICONS
// ============================================================
function IconDoc() { return <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>; }
function IconUpload() { return <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>; }
function IconChat() { return <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" /></svg>; }
function IconCompare() { return <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>; }
function IconGear() { return <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>; }

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
  return <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${s.bg} border ${s.border} ${s.text}`}>{status}</span>;
}

function RiskBadge({ level }) {
  const map = {
    low: { bg: "bg-emerald-500/15", text: "text-emerald-300" },
    medium: { bg: "bg-amber-500/15", text: "text-amber-300" },
    high: { bg: "bg-red-500/15", text: "text-red-300" },
  };
  const s = map[level] || map.low;
  return <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase ${s.bg} ${s.text}`}>{level}</span>;
}

// ============================================================
// DOCUMENT LIBRARY PAGE
// ============================================================
function DocumentLibrary({ documents, onRefresh, loading }) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-bold text-white">Document Library</h2>
          <p className="text-xs text-white/40 mt-0.5">{documents.length} specification documents</p>
        </div>
        <button onClick={onRefresh} disabled={loading} className="px-4 py-2 rounded-lg text-xs font-semibold bg-element-blue/20 text-element-cyan border border-element-blue/30 hover:bg-element-blue/30 disabled:opacity-50 transition-all">
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        {documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl glass flex items-center justify-center mb-4"><IconDoc /></div>
            <h3 className="text-sm font-semibold text-white/60">No documents yet</h3>
            <p className="text-xs text-white/30 mt-1">Upload PDF specifications to get started</p>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((doc, i) => (
              <div key={doc.document_id || i} className="glass-card rounded-xl p-4 fade-up" style={{ animationDelay: `${i * 40}ms` }}>
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="text-sm font-semibold text-white truncate">{doc.original_file_name}</h4>
                      <StatusBadge status={doc.status || doc.parsing_status || "unknown"} />
                    </div>
                    <div className="flex items-center gap-4 text-[10px] text-white/40">
                      {doc.spec_number && <span className="font-mono text-element-cyan">{doc.spec_number}</span>}
                      {doc.aedms_number && <span className="font-mono">{doc.aedms_number}</span>}
                      {doc.issue_year && <span>Year: {doc.issue_year}</span>}
                      {doc.page_count && <span>{doc.page_count} pages</span>}
                      {doc.title && <span className="truncate max-w-[200px]">{doc.title}</span>}
                    </div>
                  </div>
                  <div className="text-right text-[9px] text-white/25 ml-4">
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
// PIPELINE STEP COMPONENT
// ============================================================
function PipelineStepRow({ step, index }) {
  const statusIcon = {
    pending: <div className="w-5 h-5 rounded-full border border-white/20" />,
    running: <div className="w-5 h-5 rounded-full border-2 border-element-cyan/30 border-t-element-cyan spinner" />,
    completed: <div className="w-5 h-5 rounded-full bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center"><svg className="w-3 h-3 text-emerald-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg></div>,
    failed: <div className="w-5 h-5 rounded-full bg-red-500/20 border border-red-500/50 flex items-center justify-center"><svg className="w-3 h-3 text-red-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/></svg></div>,
  };
  const barColor = { pending: "bg-white/5", running: "bg-element-cyan/20", completed: "bg-emerald-500/10", failed: "bg-red-500/10" };

  return (
    <div className={`flex items-start gap-3 px-4 py-3 rounded-lg ${barColor[step.status] || "bg-white/5"} transition-all duration-300`}>
      <div className="flex-shrink-0 mt-0.5">{statusIcon[step.status]}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className={`text-xs font-semibold ${step.status === "running" ? "text-element-cyan" : step.status === "completed" ? "text-emerald-300" : step.status === "failed" ? "text-red-300" : "text-white/40"}`}>
            {step.label}
          </span>
          {step.duration_ms != null && (
            <span className="text-[9px] text-white/30 font-mono ml-2">{(step.duration_ms / 1000).toFixed(1)}s</span>
          )}
        </div>
        {step.detail && (
          <p className={`text-[10px] mt-0.5 font-mono ${step.status === "failed" ? "text-red-300/70" : "text-white/30"}`}>{step.detail}</p>
        )}
      </div>
    </div>
  );
}

// ============================================================
// UPLOAD PAGE WITH LIVE PIPELINE PROGRESS
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

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const startPolling = (docId) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const r = await get(`/api/documents/${docId}/progress`);
        setProgress(r);
        if (r.status === "completed" || r.status === "failed") {
          stopPolling();
          setProcessing(false);
          setDone(true);
          if (r.status === "completed" && onUploadComplete) onUploadComplete();
        }
      } catch (e) {}
    }, 1500);
  };

  useEffect(() => { return () => stopPolling(); }, []);

  const handleDrop = useCallback(async (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith(".pdf"));
    if (files.length > 0) await processFile(files[0]);
  }, []);

  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (file) await processFile(file);
  };

  const processFile = async (file) => {
    setProcessing(true);
    setError(null);
    setProgress(null);
    setDone(false);
    setDocumentId(null);
    try {
      const result = await uploadFile("/api/documents/upload", file);
      setDocumentId(result.document_id);
      startPolling(result.document_id);
    } catch (err) {
      setError(err.message);
      setProcessing(false);
    }
  };

  const reset = () => {
    setProcessing(false);
    setDocumentId(null);
    setProgress(null);
    setError(null);
    setDone(false);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-4 border-b border-white/5">
        <h2 className="text-lg font-bold text-white">Upload Document</h2>
        <p className="text-xs text-white/40 mt-0.5">Drag and drop PDF specifications — real-time pipeline progress below</p>
      </div>
      <div className="flex-1 p-6 overflow-y-auto">
        {!processing && !done && (
          <div className="flex flex-col items-center justify-center h-full">
            <div
              className={`drop-zone rounded-2xl p-12 text-center w-full max-w-xl cursor-pointer ${isDragging ? "active" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-2xl glass flex items-center justify-center">
                  <IconUpload />
                </div>
                <div className="text-sm text-white/70 font-medium">Drop PDF here or click to browse</div>
                <div className="text-[10px] text-white/30">Supports engineering specifications up to 100MB</div>
              </div>
              <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={handleFileSelect} />
            </div>
            {error && (
              <div className="mt-6 w-full max-w-xl p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-300 fade-up">
                <strong>Error:</strong> {error}
              </div>
            )}
          </div>
        )}

        {(processing || done) && progress && (
          <div className="max-w-2xl mx-auto fade-up">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-white">Pipeline Execution</h3>
                <p className="text-[10px] text-white/30 mt-0.5">Document ID: <span className="font-mono text-element-cyan">{documentId}</span></p>
              </div>
              <div className="text-right">
                <div className={`text-xs font-bold ${progress.status === "completed" ? "text-emerald-400" : progress.status === "failed" ? "text-red-400" : "text-element-cyan"}`}>
                  {progress.status === "completed" ? "COMPLETED" : progress.status === "failed" ? "FAILED" : "RUNNING"}
                </div>
                <div className="text-[10px] text-white/30">{progress.completed_steps}/{progress.total_steps} steps</div>
              </div>
            </div>

            {/* Progress bar */}
            <div className="w-full h-2 rounded-full bg-white/5 mb-5 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${progress.status === "completed" ? "bg-emerald-500" : progress.status === "failed" ? "bg-red-500" : "bg-element-cyan"}`}
                style={{ width: `${progress.percent}%` }}
              />
            </div>

            {/* Steps */}
            <div className="space-y-2">
              {progress.steps.map((step, i) => (
                <PipelineStepRow key={step.step_name} step={step} index={i} />
              ))}
            </div>

            {done && (
              <div className="mt-6 flex justify-center">
                <button onClick={reset} className="px-6 py-2 rounded-lg text-xs font-semibold bg-element-blue/20 text-element-cyan border border-element-blue/30 hover:bg-element-blue/30 transition-all">
                  Upload Another Document
                </button>
              </div>
            )}
          </div>
        )}

        {processing && !progress && (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="w-12 h-12 border-2 border-element-cyan/30 border-t-element-cyan rounded-full spinner" />
            <p className="text-sm text-white/50 mt-4">Starting pipeline...</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// CHATBOT PAGE
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
    setLoading(true);
    setCitations([]);

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
    "Which version is current?",
    "Show me all sections related to recertification.",
    "What are the requirements for certificate of conformance?",
    "List all testing codes mentioned in the document.",
    "Compare mechanical property testing requirements.",
  ];

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-4 border-b border-white/5">
        <h2 className="text-lg font-bold text-white">Specification Assistant</h2>
        <p className="text-xs text-white/40 mt-0.5">Ask questions across all engineering specifications • RAG-powered</p>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-1">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full">
                <div className="w-14 h-14 rounded-2xl glass flex items-center justify-center mb-4">
                  <IconChat />
                </div>
                <h3 className="text-sm font-semibold text-white/60 mb-4">Ask about your specifications</h3>
                <div className="grid grid-cols-2 gap-2 max-w-lg">
                  {suggestions.map((s, i) => (
                    <button key={i} onClick={() => sendMessage(s)} className="px-3 py-2.5 rounded-lg glass border border-white/6 text-[11px] text-white/50 hover:text-white hover:border-white/20 transition-all text-left">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} mb-4 ${msg.role === "user" ? "slide-right" : "slide-left"}`}>
                {msg.role !== "user" && (
                  <div className="flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center mr-2.5 bg-element-blue/10 border border-element-blue/20">
                    <IconChat />
                  </div>
                )}
                <div className={`max-w-[75%] rounded-2xl px-4 py-3 ${msg.role === "user" ? "bg-gradient-to-br from-element-blue to-element-blue-dark text-white shadow-glow rounded-br-sm" : "glass-strong text-white/90 rounded-bl-sm"}`}>
                  <div className="text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: md(msg.content) }} />
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex items-start mb-4 slide-left">
                <div className="flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center mr-2.5 bg-element-blue/10 border border-element-blue/20">
                  <IconChat />
                </div>
                <div className="glass rounded-xl px-4 py-3 flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-element-cyan typing-dot" />
                  <div className="w-1.5 h-1.5 rounded-full bg-element-cyan typing-dot" />
                  <div className="w-1.5 h-1.5 rounded-full bg-element-cyan typing-dot" />
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="px-6 py-4 border-t border-white/5">
            <form onSubmit={(e) => { e.preventDefault(); sendMessage(); }} className="flex gap-3">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about your engineering specifications..."
                className="flex-1 glass-input rounded-xl px-4 py-3 text-sm text-white placeholder-white/30"
                disabled={loading}
              />
              <button type="submit" disabled={!input.trim() || loading} className="px-5 py-3 rounded-xl text-xs font-semibold bg-gradient-to-r from-element-blue to-element-blue-dark text-white hover:shadow-glow transition-all disabled:opacity-30">
                Send
              </button>
            </form>
          </div>
        </div>

        {citations.length > 0 && (
          <div className="w-72 border-l border-white/5 overflow-y-auto p-4">
            <h3 className="text-[10px] font-bold text-white/60 uppercase tracking-wider mb-3">Sources</h3>
            <div className="space-y-2">
              {citations.map((c, i) => (
                <div key={i} className="glass-card rounded-lg p-3 fade-up" style={{ animationDelay: `${i * 50}ms` }}>
                  <div className="text-[10px] font-medium text-white/70 truncate">{c.document_name}</div>
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
// COMPARE PAGE (Multi-document)
// ============================================================
function ComparePage({ documents }) {
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const toggleDoc = (docId) => {
    setSelectedDocs(prev => prev.includes(docId) ? prev.filter(d => d !== docId) : [...prev, docId]);
  };

  const runCompare = async () => {
    if (selectedDocs.length < 2) return;
    setLoading(true);
    setResults(null);
    try {
      const result = await post("/api/compare", { document_ids: selectedDocs });
      setResults(result);
    } catch (err) {
      setResults({ error: err.message });
    }
    setLoading(false);
  };

  const downloadDocx = async () => {
    if (!results || !results.conclusion) return;
    setDownloading(true);
    try {
      const r = await fetch(`${API}/api/compare/download-docx`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_ids: selectedDocs, conclusion: results.conclusion }),
      });
      if (!r.ok) throw new Error("Download failed");
      const blob = await r.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = r.headers.get("Content-Disposition")?.split("filename=")[1]?.replace(/"/g, "") || "Comparison_Report.docx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("Failed to download report: " + err.message);
    }
    setDownloading(false);
  };

  const changeTypeColors = {
    added: "text-emerald-300 bg-emerald-500/10 border-emerald-500/20",
    removed: "text-red-300 bg-red-500/10 border-red-500/20",
    modified: "text-amber-300 bg-amber-500/10 border-amber-500/20",
    unchanged: "text-slate-300 bg-slate-500/10 border-slate-500/20",
  };

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-4 border-b border-white/5">
        <h2 className="text-lg font-bold text-white">Compare Versions</h2>
        <p className="text-xs text-white/40 mt-0.5">Select 2 or more documents • AI compares all versions with conclusions</p>
      </div>

      <div className="px-6 py-4 border-b border-white/5">
        <div className="flex items-center justify-between mb-3">
          <label className="text-[10px] text-white/40 uppercase tracking-wider font-medium">Select documents to compare ({selectedDocs.length} selected)</label>
          <button onClick={runCompare} disabled={selectedDocs.length < 2 || loading} className="px-5 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-element-blue to-element-blue-dark text-white hover:shadow-glow transition-all disabled:opacity-30 flex items-center gap-2">
            {loading && <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full spinner" />}
            {loading ? "Analyzing..." : `Compare ${selectedDocs.length} Documents`}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {documents.map(d => {
            const isSelected = selectedDocs.includes(d.document_id);
            return (
              <button key={d.document_id} onClick={() => toggleDoc(d.document_id)}
                className={`px-3 py-2 rounded-lg text-[11px] border transition-all ${isSelected ? "bg-element-blue/15 border-element-blue/40 text-element-cyan font-medium" : "glass border-white/8 text-white/50 hover:border-white/20"}`}>
                {d.original_file_name} <span className="text-white/30">({d.issue_year || "?"})</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {!results && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-14 h-14 rounded-2xl glass flex items-center justify-center mb-4"><IconCompare /></div>
            <h3 className="text-sm font-semibold text-white/60">Select 2+ documents to compare</h3>
            <p className="text-xs text-white/30 mt-1 max-w-sm">AI will analyze section-by-section differences across all versions, assess risk, and provide a conclusion</p>
            <p className="text-xs text-white/20 mt-3">You can also compare in Chat: "Compare the 2020 and 2026 versions"</p>
          </div>
        )}

        {results && results.error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-300">{results.error}</div>
        )}

        {results && !results.error && (
          <div className="space-y-6">
            {/* Download DOCX button */}
            {results.conclusion && (
              <div className="flex justify-end fade-up">
                <button onClick={downloadDocx} disabled={downloading} className="px-5 py-2.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-emerald-600 to-emerald-700 text-white hover:from-emerald-500 hover:to-emerald-600 shadow-lg transition-all disabled:opacity-50 flex items-center gap-2">
                  {downloading ? (
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full spinner" />
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>
                  )}
                  {downloading ? "Generating..." : "Download Report (.docx)"}
                </button>
              </div>
            )}

            {/* Conclusion */}
            {results.conclusion && (
              <div className="glass-card rounded-xl p-5 border-l-4 border-element-blue fade-up">
                <h3 className="text-xs font-bold text-element-cyan uppercase tracking-wider mb-3 flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
                  AI Conclusion
                </h3>
                <div className="text-[12px] text-white/80 leading-relaxed whitespace-pre-line" dangerouslySetInnerHTML={{ __html: md(results.conclusion) }} />
              </div>
            )}

            {/* Pairwise comparisons */}
            {(results.pairwise_comparisons || []).map((pair, pi) => (
              <div key={pi} className="space-y-3 fade-up" style={{ animationDelay: `${pi * 100}ms` }}>
                <div className="flex items-center gap-3">
                  <h3 className="text-xs font-bold text-white/70">
                    {pair.old_document?.original_file_name} → {pair.new_document?.original_file_name}
                  </h3>
                  <div className="flex items-center gap-2 text-[9px]">
                    <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">{pair.stats?.modified || 0} modified</span>
                    <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">{pair.stats?.added || 0} added</span>
                    <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-300 border border-red-500/20">{pair.stats?.removed || 0} removed</span>
                    {pair.stats?.high_risk > 0 && <span className="px-2 py-0.5 rounded bg-red-500/15 text-red-300 border border-red-500/30 font-bold">{pair.stats.high_risk} HIGH RISK</span>}
                  </div>
                </div>

                {(pair.sections || []).filter(s => s.change_type !== "unchanged").map((comp, i) => (
                  <div key={i} className="glass-card rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-white/30">§{comp.section_number}</span>
                        <span className="text-xs font-semibold text-white/80">{comp.section_title}</span>
                        <span className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase border ${changeTypeColors[comp.change_type] || changeTypeColors.unchanged}`}>{comp.change_type}</span>
                      </div>
                      <RiskBadge level={comp.risk_level} />
                    </div>
                    {comp.change_summary && <p className="text-[11px] text-white/50 leading-relaxed">{comp.change_summary}</p>}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// SETUP PAGE
// ============================================================
function SetupPage() {
  const [setupResult, setSetupResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const runSetup = async () => {
    setLoading(true);
    try {
      const result = await post("/api/setup", {});
      setSetupResult(result);
    } catch (err) {
      setSetupResult({ error: err.message });
    }
    setLoading(false);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-4 border-b border-white/5">
        <h2 className="text-lg font-bold text-white">Platform Setup</h2>
        <p className="text-xs text-white/40 mt-0.5">Initialize Unity Catalog tables and Vector Search index</p>
      </div>
      <div className="flex-1 p-6 flex flex-col items-center justify-center">
        <div className="glass-card rounded-2xl p-8 max-w-md w-full text-center">
          <div className="w-14 h-14 rounded-2xl glass flex items-center justify-center mx-auto mb-4"><IconGear /></div>
          <h3 className="text-sm font-semibold text-white/80 mb-2">Initialize Infrastructure</h3>
          <p className="text-xs text-white/40 mb-6">Creates UC catalog, schema, volume, 7 Delta tables, and Vector Search index</p>
          <button onClick={runSetup} disabled={loading} className="px-6 py-3 rounded-xl text-xs font-semibold bg-gradient-to-r from-element-blue to-element-blue-dark text-white hover:shadow-glow transition-all disabled:opacity-50 flex items-center gap-2 mx-auto">
            {loading && <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full spinner" />}
            {loading ? "Setting up..." : "Run Setup"}
          </button>
        </div>

        {setupResult && (
          <div className="mt-6 glass-card rounded-xl p-5 max-w-md w-full fade-up">
            {setupResult.error ? (
              <div className="text-xs text-red-300">{setupResult.error}</div>
            ) : (
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold text-white/60 uppercase tracking-wider mb-2">Results</h4>
                {setupResult.uc_tables && Object.entries(setupResult.uc_tables).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between text-[11px]">
                    <span className="text-white/50">{key}</span>
                    <span className={val ? "text-emerald-400" : "text-red-400"}>{val ? "✓" : "✗"}</span>
                  </div>
                ))}
                <div className="flex items-center justify-between text-[11px] pt-2 border-t border-white/5">
                  <span className="text-white/50">Vector Search Endpoint</span>
                  <span className={setupResult.vector_search_endpoint ? "text-emerald-400" : "text-red-400"}>{setupResult.vector_search_endpoint ? "✓" : "✗"}</span>
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-white/50">Vector Search Index</span>
                  <span className={setupResult.vector_search_index ? "text-emerald-400" : "text-red-400"}>{setupResult.vector_search_index ? "✓" : "✗"}</span>
                </div>
              </div>
            )}
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
    try {
      const result = await get("/api/documents");
      setDocuments(result.documents || []);
    } catch (e) {
      console.error("Failed to load docs:", e);
    }
    setDocsLoading(false);
  };

  useEffect(() => { loadDocuments(); }, []);

  const NAV_ITEMS = [
    { id: "library", label: "Documents", icon: IconDoc },
    { id: "upload", label: "Upload", icon: IconUpload },
    { id: "chat", label: "Chat", icon: IconChat },
    { id: "compare", label: "Compare", icon: IconCompare },
    { id: "setup", label: "Setup", icon: IconGear },
  ];

  return (
    <div className="h-screen flex">
      {/* Sidebar */}
      <div className="w-56 glass-sidebar flex flex-col">
        <div className="p-4 border-b border-white/5 flex items-center gap-3">
          <img src="/images/element-logo.png" alt="Element" className="h-7" onError={(e) => { e.target.style.display = "none"; }} />
          <div>
            <div className="text-xs font-bold text-white/90">Spec Intelligence</div>
            <div className="text-[9px] text-white/40">Document Platform</div>
          </div>
        </div>

        <nav className="flex-1 p-2 space-y-1">
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              onClick={() => setPage(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${page === item.id ? "glass-strong text-white border border-white/10" : "text-white/50 hover:text-white/80 hover:bg-white/3"}`}
            >
              <item.icon />
              {item.label}
            </button>
          ))}
        </nav>

        <div className="p-3 border-t border-white/5">
          <div className="text-[9px] text-white/30 space-y-1">
            <div className="flex justify-between"><span>Documents</span><span className="text-white/50">{documents.length}</span></div>
            <div className="flex justify-between"><span>Engine</span><span className="text-emerald-400">Llama 3.3 70B</span></div>
            <div className="flex justify-between"><span>Storage</span><span className="text-white/50">Unity Catalog</span></div>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <img src="/images/databricks-logo.png" alt="Databricks" className="h-3 opacity-40" onError={(e) => { e.target.style.display = "none"; }} />
            <span className="text-[8px] text-white/20">Powered by Databricks</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden bg-gradient-to-br from-[#0a1020] via-[#0d1628] to-[#0a1020]">
        {page === "library" && <DocumentLibrary documents={documents} onRefresh={loadDocuments} loading={docsLoading} />}
        {page === "upload" && <UploadPage onUploadComplete={loadDocuments} />}
        {page === "chat" && <ChatPage />}
        {page === "compare" && <ComparePage documents={documents} />}
        {page === "setup" && <SetupPage />}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
