import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { addAlertNote, getAlert, getRelatedEvents, updateAlert } from "../api/client.js";
import EmptyState from "../components/EmptyState.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import EventTable from "../components/EventTable.jsx";
import SeverityBadge from "../components/SeverityBadge.jsx";
import Spinner from "../components/Spinner.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { getAnalystName, saveAnalystName } from "../utils/analyst.js";
import { formatDateTime } from "../utils/format.js";

const STATUSES = ["New", "In Progress", "Closed"];
const VERDICTS = ["Suspected", "Confirmed", "False Positive", "Benign"];

export default function AlertDetail() {
  const { id } = useParams();
  const [alert, setAlert] = useState(null);
  const [related, setRelated] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    getAlert(id)
      .then(setAlert)
      .catch((err) => setError(err.message));
    getRelatedEvents(id)
      .then(setRelated)
      .catch(() => setRelated([]));
  }, [id]);

  useEffect(load, [load]);

  if (error) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorBanner message={error} />
      </div>
    );
  }
  if (!alert) return <Spinner />;

  const evidenceEntries = Object.entries(alert.evidence || {}).filter(([, v]) => v !== null && v !== "");

  return (
    <div>
      <BackLink />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <SeverityBadge severity={alert.severity} />
        <StatusBadge value={alert.status} />
        <StatusBadge value={alert.verdict} />
        <span className="font-mono text-xs text-slate-500">Alert #{alert.id}</span>
      </div>
      <h1 className="page-title mt-2">{alert.title}</h1>
      <p className="page-subtitle">
        {alert.rule_id} · {alert.rule_name} · MITRE ATT&amp;CK {alert.mitre_technique} · {formatDateTime(alert.first_seen)} →{" "}
        {formatDateTime(alert.last_seen)}
      </p>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 space-y-6">
          <section className="card">
            <h2 className="section-title">Why this alert fired</h2>
            <p className="mt-2 text-sm text-slate-200">{alert.detection_explanation}</p>
            <p className="mt-2 text-sm text-slate-400">{alert.description}</p>
            {evidenceEntries.length > 0 && (
              <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2 rounded-lg bg-slate-950 p-3 text-sm sm:grid-cols-2">
                {evidenceEntries.map(([key, value]) => (
                  <div key={key} className="flex gap-2">
                    <dt className="text-slate-500">{key.replaceAll("_", " ")}:</dt>
                    <dd className="break-all font-mono text-xs leading-5 text-slate-200">
                      {Array.isArray(value) ? value.join(", ") : String(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </section>

          <section className="card">
            <h2 className="section-title">Evidence events ({alert.events.length})</h2>
            <p className="mt-1 text-xs text-slate-500">The log rows that matched the rule. Use “Raw” to see each row exactly as uploaded.</p>
            <div className="mt-3">
              <EventTable events={alert.events} showRaw />
            </div>
          </section>

          <section className="card">
            <h2 className="section-title">Related events ({related.length})</h2>
            <p className="mt-1 text-xs text-slate-500">
              Other events with the same source IP, user or host within 60 minutes of this alert. Use them for context.
            </p>
            <div className="mt-3">
              {related.length ? <EventTable events={related} /> : <EmptyState title="No related events found." />}
            </div>
          </section>

          <Notes alert={alert} onAdded={load} />
        </div>

        <div className="space-y-6">
          <Triage alert={alert} onUpdated={setAlert} />

          <section className="card">
            <h2 className="section-title">Incident</h2>
            {alert.incident_id ? (
              <p className="mt-2 text-sm text-slate-300">
                Linked to{" "}
                <Link to={`/incidents/${alert.incident_id}`} className="text-cyan-300 hover:underline">
                  #{alert.incident_id} {alert.incident_title}
                </Link>
              </p>
            ) : (
              <>
                <p className="mt-2 text-sm text-slate-400">Escalate this alert when it needs coordinated handling.</p>
                <Link to={`/incidents/new?alert=${alert.id}`} className="btn-primary mt-3 w-full">
                  Create incident from this alert
                </Link>
              </>
            )}
          </section>

          <section className="card">
            <h2 className="section-title">Rule context</h2>
            <h3 className="mt-3 text-xs font-semibold uppercase tracking-wider text-amber-300/90">Limitations</h3>
            <p className="mt-1 text-sm text-slate-400">{alert.rule_limitations}</p>
            <h3 className="mt-3 text-xs font-semibold uppercase tracking-wider text-amber-300/90">Possible false positives</h3>
            <p className="mt-1 text-sm text-slate-400">{alert.rule_false_positives}</p>
          </section>
        </div>
      </div>
    </div>
  );
}

function BackLink() {
  return (
    <Link to="/alerts" className="text-sm text-slate-400 hover:text-cyan-300">
      ← All alerts
    </Link>
  );
}

function Triage({ alert, onUpdated }) {
  const [status, setStatus] = useState(alert.status);
  const [verdict, setVerdict] = useState(alert.verdict);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const confirming = verdict === "Confirmed" && alert.verdict !== "Confirmed";
  const changed = status !== alert.status || verdict !== alert.verdict;
  const noteTooShort = confirming && note.trim().length < 10;

  async function save() {
    setSaving(true);
    setMessage(null);
    const author = getAnalystName();
    const changes = { author };
    if (status !== alert.status) changes.status = status;
    if (verdict !== alert.verdict) changes.verdict = verdict;
    if (note.trim()) changes.note = note.trim();
    try {
      const updated = await updateAlert(alert.id, changes);
      onUpdated(updated);
      setNote("");
      setMessage({ type: "ok", text: "Alert updated." });
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card" data-testid="triage">
      <h2 className="section-title">Triage</h2>
      <div className="mt-3 space-y-3">
        <div>
          <label className="label" htmlFor="alert-status">Status</label>
          <select id="alert-status" className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="alert-verdict">Verdict</label>
          <select id="alert-verdict" className="input" value={verdict} onChange={(e) => setVerdict(e.target.value)}>
            {VERDICTS.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="alert-justification">
            {confirming ? "Justification (required)" : "Note (optional)"}
          </label>
          <textarea
            id="alert-justification"
            className="input min-h-[80px]"
            maxLength={2000}
            placeholder={confirming ? "What evidence confirms this is malicious?" : "Why are you making this change?"}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          {confirming && (
            <p className="mt-1 text-xs text-amber-300">
              Confirmed means you verified malicious activity. Describe the evidence (at least 10 characters).
            </p>
          )}
        </div>
        <button type="button" className="btn-primary w-full" disabled={saving || !changed || noteTooShort} onClick={save}>
          {saving ? "Saving..." : "Update alert"}
        </button>
        {message && <p className={`text-sm ${message.type === "ok" ? "text-emerald-300" : "text-rose-300"}`}>{message.text}</p>}
      </div>
      <div className="mt-4 rounded-lg bg-slate-950 p-3 text-xs text-slate-400">
        <p><b className="text-amber-300">Suspected</b>: a rule matched; not yet verified.</p>
        <p className="mt-1"><b className="text-rose-300">Confirmed</b>: analyst verified malicious activity.</p>
        <p className="mt-1"><b className="text-slate-200">False Positive</b>: rule matched, activity not malicious.</p>
        <p className="mt-1"><b className="text-emerald-300">Benign</b>: real but expected or authorized activity.</p>
      </div>
    </section>
  );
}

function Notes({ alert, onAdded }) {
  const [note, setNote] = useState("");
  const [author, setAuthor] = useState(getAnalystName);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!note.trim()) return;
    setSaving(true);
    setError("");
    try {
      const name = author.trim() || "analyst";
      saveAnalystName(name);
      await addAlertNote(alert.id, note.trim(), name);
      setNote("");
      onAdded();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card" data-testid="notes">
      <h2 className="section-title">Investigation notes ({alert.notes.length})</h2>
      <ol className="mt-3 space-y-3">
        {alert.notes.length === 0 && <li className="text-sm text-slate-500">No notes yet.</li>}
        {alert.notes.map((n) => {
          const automatic = /^(Status|Verdict) changed from /.test(n.note);
          return (
            <li key={n.id} className={`rounded-lg px-3 py-2 text-sm ${automatic ? "bg-transparent text-slate-500" : "bg-slate-950 text-slate-200"}`}>
              <p className="whitespace-pre-wrap break-words">{n.note}</p>
              <p className="mt-1 text-xs text-slate-500">
                {n.author} · {formatDateTime(n.created_at)}
              </p>
            </li>
          );
        })}
      </ol>
      <form onSubmit={submit} className="mt-4 space-y-2">
        <textarea
          className="input min-h-[80px]"
          placeholder="Add an investigation note (what you checked, what you found)"
          maxLength={2000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          aria-label="New note"
        />
        <div className="flex flex-wrap items-center gap-2">
          <input className="input w-40" value={author} maxLength={100} onChange={(e) => setAuthor(e.target.value)} aria-label="Your name" />
          <button type="submit" className="btn-secondary" disabled={saving || !note.trim()}>
            {saving ? "Adding..." : "Add note"}
          </button>
          {error && <span className="text-sm text-rose-300">{error}</span>}
        </div>
      </form>
    </section>
  );
}
