import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { createIncident, getAlert, getAlerts } from "../api/client.js";
import ErrorBanner from "../components/ErrorBanner.jsx";
import SeverityBadge from "../components/SeverityBadge.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { getAnalystName } from "../utils/analyst.js";

const SEVERITIES = ["Low", "Medium", "High", "Critical"];
const PRIORITIES = [
  { value: "P1", label: "P1 – respond immediately" },
  { value: "P2", label: "P2 – respond within hours" },
  { value: "P3", label: "P3 – within one business day" },
  { value: "P4", label: "P4 – when capacity allows" },
];

export default function IncidentCreate() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const fromAlert = params.get("alert");

  const [form, setForm] = useState({ title: "", description: "", severity: "Medium", priority: "P3", assigned_to: "" });
  const [selected, setSelected] = useState(() => new Set(fromAlert ? [Number(fromAlert)] : []));
  const [available, setAvailable] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Alerts that are not in an incident yet can be attached.
  useEffect(() => {
    getAlerts({ in_incident: false, limit: 200 })
      .then((data) => setAvailable(data.items))
      .catch((err) => setError(err.message));
  }, []);

  // Pre-fill the form from the alert the analyst came from.
  useEffect(() => {
    if (!fromAlert) return;
    getAlert(fromAlert)
      .then((a) =>
        setForm((f) => ({
          ...f,
          title: a.title,
          description: `${a.description}\n\nDetection: ${a.detection_explanation}`,
          severity: a.severity,
          priority: a.severity === "Critical" ? "P1" : a.severity === "High" ? "P2" : "P3",
        })),
      )
      .catch((err) => setError(err.message));
  }, [fromAlert]);

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function toggle(id) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const incident = await createIncident({
        ...form,
        title: form.title.trim(),
        assigned_to: form.assigned_to.trim() || null,
        alert_ids: [...selected],
        author: getAnalystName(),
      });
      navigate(`/incidents/${incident.id}`);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <div>
      <Link to="/incidents" className="text-sm text-slate-400 hover:text-cyan-300">← All incidents</Link>
      <h1 className="page-title mt-3">New incident</h1>
      <p className="page-subtitle">Group related alerts into a case. The incident starts with status New.</p>

      <form onSubmit={submit} className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="card space-y-4">
          <div>
            <label className="label" htmlFor="inc-title">Title</label>
            <input id="inc-title" className="input" required minLength={3} maxLength={255} value={form.title} onChange={(e) => update("title", e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="inc-description">Description</label>
            <textarea id="inc-description" className="input min-h-[140px]" maxLength={5000} value={form.description} onChange={(e) => update("description", e.target.value)} />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="inc-severity">Severity</label>
              <select id="inc-severity" className="input" value={form.severity} onChange={(e) => update("severity", e.target.value)}>
                {SEVERITIES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="inc-priority">Priority</label>
              <select id="inc-priority" className="input" value={form.priority} onChange={(e) => update("priority", e.target.value)}>
                {PRIORITIES.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="inc-assignee">Assigned to</label>
              <input id="inc-assignee" className="input" maxLength={100} placeholder="optional" value={form.assigned_to} onChange={(e) => update("assigned_to", e.target.value)} />
            </div>
          </div>
          <ErrorBanner message={error} />
          <button type="submit" className="btn-primary" disabled={saving || form.title.trim().length < 3}>
            {saving ? "Creating..." : `Create incident${selected.size ? ` with ${selected.size} alert${selected.size > 1 ? "s" : ""}` : ""}`}
          </button>
        </div>

        <div className="card h-fit">
          <h2 className="section-title">Link alerts ({selected.size} selected)</h2>
          <p className="mt-1 text-xs text-slate-500">Only alerts that are not already in an incident are listed.</p>
          <ul className="mt-3 max-h-[28rem] space-y-2 overflow-y-auto">
            {available.length === 0 && <li className="text-sm text-slate-500">No unlinked alerts.</li>}
            {available.map((a) => (
              <li key={a.id}>
                <label className="flex cursor-pointer gap-3 rounded-lg border border-slate-800 p-2 hover:bg-slate-800/40">
                  <input type="checkbox" className="mt-1 h-4 w-4 accent-cyan-500" checked={selected.has(a.id)} onChange={() => toggle(a.id)} />
                  <span className="min-w-0">
                    <span className="flex flex-wrap items-center gap-1.5">
                      <SeverityBadge severity={a.severity} />
                      <StatusBadge value={a.verdict} />
                      <span className="font-mono text-xs text-slate-500">#{a.id}</span>
                    </span>
                    <span className="mt-1 block text-sm text-slate-200">{a.title}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      </form>
    </div>
  );
}
