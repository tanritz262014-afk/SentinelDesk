import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addIncidentNote,
  downloadIncidentReport,
  getAlerts,
  getIncident,
  linkIncidentAlerts,
  updateIncident,
} from "../api/client.js";
import ErrorBanner from "../components/ErrorBanner.jsx";
import SeverityBadge from "../components/SeverityBadge.jsx";
import Spinner from "../components/Spinner.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { getAnalystName } from "../utils/analyst.js";
import { formatDateTime } from "../utils/format.js";

// Same rules as the backend (ALLOWED_TRANSITIONS in routers/incidents.py).
const NEXT_STATUSES = {
  New: ["Investigating", "Escalated", "Resolved"],
  Investigating: ["Escalated", "Resolved"],
  Escalated: ["Investigating", "Resolved"],
  Resolved: ["Investigating"],
};
const ACTION_LABELS = {
  Investigating: "Start investigating",
  Escalated: "Escalate to L2 / IR",
  Resolved: "Resolve",
};
const WORKFLOW = ["New", "Investigating", "Escalated", "Resolved"];
const TIMELINE_COLORS = {
  created: "bg-cyan-400",
  status_change: "bg-indigo-400",
  updated: "bg-slate-400",
  note: "bg-emerald-400",
  alert_linked: "bg-amber-400",
};

export default function IncidentDetail() {
  const { id } = useParams();
  const [incident, setIncident] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    getIncident(id)
      .then(setIncident)
      .catch((err) => setError(err.message));
  }, [id]);

  useEffect(load, [load]);

  if (error && !incident) {
    return (
      <div className="space-y-4">
        <Link to="/incidents" className="text-sm text-slate-400 hover:text-cyan-300">← All incidents</Link>
        <ErrorBanner message={error} />
      </div>
    );
  }
  if (!incident) return <Spinner />;

  return (
    <div>
      <Link to="/incidents" className="text-sm text-slate-400 hover:text-cyan-300">← All incidents</Link>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <SeverityBadge severity={incident.severity} />
        <span className="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-200">{incident.priority}</span>
        <StatusBadge value={incident.status} />
        <span className="font-mono text-xs text-slate-500">Incident #{incident.id}</span>
      </div>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="page-title">{incident.title}</h1>
          <p className="page-subtitle">
            Created {formatDateTime(incident.created_at)} · {incident.assigned_to ? `Assigned to ${incident.assigned_to}` : "Unassigned"}
          </p>
        </div>
        <ExportButtons incidentId={incident.id} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-6">
          <Workflow incident={incident} onUpdated={setIncident} />

          <section className="card">
            <h2 className="section-title">Description</h2>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-300">{incident.description || "No description."}</p>
            {incident.resolution_summary && (
              <>
                <h3 className="mt-4 text-xs font-semibold uppercase tracking-wider text-emerald-300">Resolution</h3>
                <p className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-300">{incident.resolution_summary}</p>
              </>
            )}
          </section>

          <LinkedAlerts incident={incident} onChanged={setIncident} />
          <Timeline incident={incident} onChanged={setIncident} />
        </div>

        <div className="space-y-6">
          <EditDetails incident={incident} onUpdated={setIncident} />
        </div>
      </div>
    </div>
  );
}

function ExportButtons({ incidentId }) {
  const [error, setError] = useState("");
  async function download(format) {
    setError("");
    try {
      await downloadIncidentReport(incidentId, format);
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <button type="button" className="btn-secondary" onClick={() => download("markdown")}>Export Markdown</button>
        <button type="button" className="btn-secondary" onClick={() => download("json")}>Export JSON</button>
      </div>
      {error && <span className="text-xs text-rose-300">{error}</span>}
    </div>
  );
}

function Workflow({ incident, onUpdated }) {
  const [resolving, setResolving] = useState(false);
  const [summary, setSummary] = useState(incident.resolution_summary || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const currentIndex = WORKFLOW.indexOf(incident.status);

  async function changeStatus(status) {
    if (status === "Resolved" && !resolving) {
      setResolving(true);
      return;
    }
    setSaving(true);
    setError("");
    try {
      const changes = { status, author: getAnalystName() };
      if (status === "Resolved") changes.resolution_summary = summary.trim();
      onUpdated(await updateIncident(incident.id, changes));
      setResolving(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card" data-testid="workflow">
      <h2 className="section-title">Workflow</h2>
      <ol className="mt-4 grid grid-cols-4 gap-2">
        {WORKFLOW.map((step, i) => {
          const active = step === incident.status;
          const done = i < currentIndex;
          return (
            <li
              key={step}
              className={`rounded-lg border px-2 py-2 text-center text-xs font-medium ${
                active
                  ? "border-cyan-500 bg-cyan-500/10 text-cyan-200"
                  : done
                    ? "border-slate-700 bg-slate-800/50 text-slate-300"
                    : "border-slate-800 text-slate-500"
              }`}
            >
              {step}
            </li>
          );
        })}
      </ol>

      <div className="mt-4 flex flex-wrap gap-2">
        {NEXT_STATUSES[incident.status].map((status) => (
          <button
            key={status}
            type="button"
            disabled={saving}
            onClick={() => changeStatus(status)}
            className={status === "Resolved" ? "btn-primary" : status === "Escalated" ? "btn-danger" : "btn-secondary"}
          >
            {incident.status === "Resolved" ? "Reopen" : ACTION_LABELS[status]}
          </button>
        ))}
      </div>

      {resolving && (
        <div className="mt-4 space-y-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
          <label className="label" htmlFor="resolution-summary">Resolution summary (required)</label>
          <textarea
            id="resolution-summary"
            className="input min-h-[90px]"
            maxLength={5000}
            placeholder="What was found and what was done (e.g. password reset, IP blocked, user confirmed activity)."
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
          <div className="flex gap-2">
            <button type="button" className="btn-primary" disabled={saving || summary.trim().length < 10} onClick={() => changeStatus("Resolved")}>
              Confirm resolution
            </button>
            <button type="button" className="btn-secondary" onClick={() => setResolving(false)}>Cancel</button>
          </div>
        </div>
      )}
      {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
    </section>
  );
}

function EditDetails({ incident, onUpdated }) {
  const initial = { severity: incident.severity, priority: incident.priority, assigned_to: incident.assigned_to || "" };
  const [form, setForm] = useState(initial);
  const [message, setMessage] = useState(null);
  const dirty = JSON.stringify(form) !== JSON.stringify(initial);

  useEffect(() => {
    setForm({ severity: incident.severity, priority: incident.priority, assigned_to: incident.assigned_to || "" });
  }, [incident.severity, incident.priority, incident.assigned_to]);

  async function save() {
    setMessage(null);
    const changes = { author: getAnalystName() };
    if (form.severity !== initial.severity) changes.severity = form.severity;
    if (form.priority !== initial.priority) changes.priority = form.priority;
    if (form.assigned_to !== initial.assigned_to) changes.assigned_to = form.assigned_to;
    try {
      onUpdated(await updateIncident(incident.id, changes));
      setMessage({ type: "ok", text: "Saved." });
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    }
  }

  return (
    <section className="card space-y-3">
      <h2 className="section-title">Details</h2>
      <div>
        <label className="label" htmlFor="edit-severity">Severity</label>
        <select id="edit-severity" className="input" value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
          {["Low", "Medium", "High", "Critical"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="label" htmlFor="edit-priority">Priority</label>
        <select id="edit-priority" className="input" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
          {["P1", "P2", "P3", "P4"].map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="label" htmlFor="edit-assignee">Assigned to</label>
        <input id="edit-assignee" className="input" maxLength={100} value={form.assigned_to} onChange={(e) => setForm({ ...form, assigned_to: e.target.value })} />
      </div>
      <button type="button" className="btn-secondary w-full" disabled={!dirty} onClick={save}>Save details</button>
      {message && <p className={`text-sm ${message.type === "ok" ? "text-emerald-300" : "text-rose-300"}`}>{message.text}</p>}
      <dl className="border-t border-slate-800 pt-3 text-xs text-slate-500">
        <div className="flex justify-between"><dt>Last updated</dt><dd>{formatDateTime(incident.updated_at)}</dd></div>
        <div className="mt-1 flex justify-between"><dt>Resolved</dt><dd>{formatDateTime(incident.resolved_at)}</dd></div>
      </dl>
    </section>
  );
}

function LinkedAlerts({ incident, onChanged }) {
  const [available, setAvailable] = useState([]);
  const [choice, setChoice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getAlerts({ in_incident: false, limit: 200 })
      .then((d) => setAvailable(d.items))
      .catch(() => setAvailable([]));
  }, [incident.alert_count]);

  async function link() {
    if (!choice) return;
    setError("");
    try {
      onChanged(await linkIncidentAlerts(incident.id, [Number(choice)], getAnalystName()));
      setChoice("");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="card">
      <h2 className="section-title">Linked alerts ({incident.alerts.length})</h2>
      {incident.alerts.length > 0 ? (
        <ul className="mt-3 divide-y divide-slate-800 rounded-lg border border-slate-800">
          {incident.alerts.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <SeverityBadge severity={a.severity} />
                <StatusBadge value={a.verdict} />
                <Link to={`/alerts/${a.id}`} className="truncate text-sm text-slate-200 hover:text-cyan-300 hover:underline">
                  #{a.id} {a.title}
                </Link>
              </div>
              <span className="font-mono text-xs text-slate-500">{formatDateTime(a.first_seen)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-500">No alerts linked yet.</p>
      )}
      {incident.status !== "Resolved" && available.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          <select className="input max-w-md flex-1" value={choice} onChange={(e) => setChoice(e.target.value)} aria-label="Alert to link">
            <option value="">Link another alert…</option>
            {available.map((a) => (
              <option key={a.id} value={a.id}>#{a.id} [{a.severity}] {a.title}</option>
            ))}
          </select>
          <button type="button" className="btn-secondary" disabled={!choice} onClick={link}>Link alert</button>
        </div>
      )}
      {error && <p className="mt-2 text-sm text-rose-300">{error}</p>}
    </section>
  );
}

function Timeline({ incident, onChanged }) {
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!note.trim()) return;
    setSaving(true);
    setError("");
    try {
      onChanged(await addIncidentNote(incident.id, note.trim(), getAnalystName()));
      setNote("");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card" data-testid="timeline">
      <h2 className="section-title">Timeline</h2>
      <ol className="relative mt-4 space-y-4 border-l border-slate-800 pl-5">
        {incident.timeline.map((t) => (
          <li key={t.id} className="relative">
            <span className={`absolute -left-[1.6rem] top-1.5 h-2.5 w-2.5 rounded-full ${TIMELINE_COLORS[t.entry_type] || "bg-slate-500"}`} />
            <p className={`whitespace-pre-wrap break-words text-sm ${t.entry_type === "note" ? "text-slate-100" : "text-slate-300"}`}>{t.message}</p>
            <p className="mt-0.5 text-xs text-slate-500">
              {formatDateTime(t.created_at)} · {t.author} · {t.entry_type.replace("_", " ")}
            </p>
          </li>
        ))}
      </ol>
      <form onSubmit={submit} className="mt-5 space-y-2">
        <textarea className="input min-h-[80px]" maxLength={2000} placeholder="Add a note to the timeline" aria-label="Timeline note" value={note} onChange={(e) => setNote(e.target.value)} />
        <div className="flex items-center gap-2">
          <button type="submit" className="btn-secondary" disabled={saving || !note.trim()}>{saving ? "Adding..." : "Add note"}</button>
          {error && <span className="text-sm text-rose-300">{error}</span>}
        </div>
      </form>
    </section>
  );
}
