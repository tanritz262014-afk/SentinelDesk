import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getUploads, uploadLog } from "../api/client.js";
import EmptyState from "../components/EmptyState.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import SeverityBadge from "../components/SeverityBadge.jsx";
import { formatBytes, formatDateTime } from "../utils/format.js";

// Quick checks in the browser for a friendly message. The server repeats
// every check, so these are only a convenience, not the security control.
const ALLOWED_EXTENSIONS = [".json", ".csv"];
const MAX_UPLOAD_MB = 2;

function checkFile(file) {
  const name = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return "Only .json and .csv files are accepted.";
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `The file is larger than ${MAX_UPLOAD_MB} MB.`;
  }
  if (file.size === 0) return "The file is empty.";
  return "";
}

export default function LogAnalyzer() {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null); // { message, errors }
  const [uploads, setUploads] = useState([]);

  const loadUploads = useCallback(() => {
    getUploads()
      .then(setUploads)
      .catch(() => setUploads([]));
  }, []);

  useEffect(loadUploads, [loadUploads]);

  function selectFile(selected) {
    setResult(null);
    setError(null);
    if (!selected) return;
    const problem = checkFile(selected);
    if (problem) {
      setFile(null);
      setError({ message: problem });
      return;
    }
    setFile(selected);
  }

  function clearSelection() {
    setFile(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await uploadLog(file));
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      loadUploads();
    } catch (err) {
      setError({ message: err.message, errors: err.data?.errors || [] });
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <h1 className="page-title">Security Log Analyzer</h1>
      <p className="page-subtitle">Upload JSON or CSV security logs. Valid events are stored and checked by the detection rules.</p>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          {/* Upload card */}
          <div className="card">
            <h2 className="section-title">Upload a log file</h2>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                selectFile(e.dataTransfer.files?.[0]);
              }}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
              role="button"
              tabIndex={0}
              className={`mt-3 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-10 text-center transition-colors ${
                dragging ? "border-cyan-400 bg-cyan-500/5" : "border-slate-700 hover:border-slate-500"
              }`}
            >
              <svg viewBox="0 0 24 24" className="h-8 w-8 text-slate-500" fill="none" stroke="currentColor" strokeWidth="1.6">
                <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <p className="mt-2 text-sm text-slate-300">
                Drag a file here or <span className="text-cyan-300 underline">browse</span>
              </p>
              <p className="mt-1 text-xs text-slate-500">.json or .csv · max {MAX_UPLOAD_MB} MB · contents are parsed as data, never executed</p>
              <input
                ref={inputRef}
                type="file"
                accept=".json,.csv"
                className="hidden"
                data-testid="file-input"
                onChange={(e) => selectFile(e.target.files?.[0])}
              />
            </div>

            {file && (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-950 px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate font-mono text-sm text-slate-200">{file.name}</p>
                  <p className="text-xs text-slate-500">{formatBytes(file.size)}</p>
                </div>
                <div className="flex gap-2">
                  <button type="button" className="btn-secondary" onClick={clearSelection} disabled={uploading}>
                    Clear
                  </button>
                  <button type="button" className="btn-primary" onClick={handleUpload} disabled={uploading}>
                    {uploading ? "Analyzing..." : "Upload & analyze"}
                  </button>
                </div>
              </div>
            )}

            {error && (
              <div className="mt-4">
                <ErrorBanner message={error.message}>
                  {error.errors?.length > 0 && <RowErrors errors={error.errors} />}
                </ErrorBanner>
              </div>
            )}
          </div>

          {result && <UploadResult result={result} />}

          {/* History */}
          <div className="card">
            <h2 className="section-title">Upload history</h2>
            <div className="mt-3">
              {uploads.length === 0 ? (
                <EmptyState title="No files uploaded yet." hint="Try backend/sample_data/suspicious_events.json" />
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>File</th>
                        <th>Type</th>
                        <th>Size</th>
                        <th>Accepted</th>
                        <th>Rejected</th>
                        <th>Uploaded</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {uploads.map((u) => (
                        <tr key={u.id}>
                          <td className="font-mono text-xs">{u.filename}</td>
                          <td className="uppercase">{u.file_type}</td>
                          <td>{formatBytes(u.file_size_bytes)}</td>
                          <td className="text-emerald-300">{u.accepted_rows}</td>
                          <td className={u.rejected_rows ? "text-rose-300" : ""}>{u.rejected_rows}</td>
                          <td className="whitespace-nowrap text-xs">{formatDateTime(u.uploaded_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>

        <FormatHelp />
      </div>
    </div>
  );
}

function UploadResult({ result }) {
  const stats = [
    { label: "Rows in file", value: result.total_rows, color: "text-slate-100" },
    { label: "Accepted", value: result.accepted_rows, color: "text-emerald-300" },
    { label: "Rejected", value: result.rejected_rows, color: result.rejected_rows ? "text-rose-300" : "text-slate-100" },
    { label: "Alerts generated", value: result.alerts_generated, color: result.alerts_generated ? "text-amber-300" : "text-slate-100" },
  ];
  return (
    <div className="card" data-testid="upload-result">
      <h2 className="section-title">
        Analysis result · <span className="font-mono font-normal text-slate-400">{result.filename}</span>
      </h2>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-lg bg-slate-950 px-3 py-2">
            <p className="text-[11px] uppercase tracking-wider text-slate-500">{s.label}</p>
            <p className={`text-xl font-semibold tabular-nums ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {result.alerts.length > 0 ? (
        <div className="mt-4">
          <p className="text-xs text-slate-400">
            New alerts start as <b>Suspected</b>. Open each one to investigate before deciding on a verdict.
          </p>
          <ul className="mt-2 divide-y divide-slate-800 rounded-lg border border-slate-800">
            {result.alerts.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3 px-3 py-2">
                <div className="flex min-w-0 items-center gap-3">
                  <SeverityBadge severity={a.severity} />
                  <span className="font-mono text-xs text-slate-500">{a.rule_id}</span>
                  <span className="truncate text-sm text-slate-200">{a.title}</span>
                </div>
                <Link to={`/alerts/${a.id}`} className="shrink-0 text-xs text-cyan-300 hover:underline">
                  Investigate →
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-400">No detection rule matched these events.</p>
      )}

      {result.errors.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-medium text-rose-300">Rejected rows</p>
          <RowErrors errors={result.errors} truncated={result.errors_truncated} />
        </div>
      )}
    </div>
  );
}

function RowErrors({ errors, truncated }) {
  return (
    <div className="mt-2 max-h-64 overflow-y-auto rounded-lg border border-slate-800">
      <table className="data-table">
        <thead>
          <tr>
            <th>Row</th>
            <th>Problem</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {errors.map((e, i) => (
            <tr key={`${e.row}-${i}`}>
              <td className="font-mono text-xs">{e.row}</td>
              <td className="text-rose-200">{e.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {truncated && <p className="px-3 py-2 text-xs text-slate-500">Only the first 100 problems are shown.</p>}
    </div>
  );
}

function FormatHelp() {
  const example = `[
  {
    "timestamp": "2026-10-01T09:15:02Z",
    "event_id": 4625,
    "hostname": "SRV-FILE-01",
    "username": "admin.backup",
    "source_ip": "203.0.113.45",
    "logon_type": "3"
  }
]`;
  return (
    <aside className="card h-fit space-y-4 text-sm">
      <div>
        <h2 className="section-title">Log format</h2>
        <p className="mt-1 text-slate-400">
          Required: <code className="text-cyan-300">timestamp</code> (ISO 8601) and <code className="text-cyan-300">event_id</code>.
          Optional: hostname, username, source_ip, logon_type, service_name, service_path, message.
        </p>
      </div>
      <pre className="overflow-x-auto rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-300">{example}</pre>
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Event IDs analysed</h3>
        <ul className="mt-2 space-y-1 text-slate-400">
          <li><span className="font-mono text-slate-200">4624</span> Successful logon</li>
          <li><span className="font-mono text-slate-200">4625</span> Failed logon</li>
          <li><span className="font-mono text-slate-200">4720</span> User account created</li>
          <li><span className="font-mono text-slate-200">7045</span> Service installed</li>
        </ul>
      </div>
      <p className="text-xs text-slate-500">
        Sample files are in <span className="font-mono">backend/sample_data/</span>. All demo data is synthetic.
      </p>
    </aside>
  );
}
