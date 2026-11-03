import { useEffect, useState } from "react";
import { getRules, updateRule } from "../api/client.js";
import ErrorBanner from "../components/ErrorBanner.jsx";
import SeverityBadge from "../components/SeverityBadge.jsx";
import Spinner from "../components/Spinner.jsx";
import { formatDateTime } from "../utils/format.js";

const SEVERITIES = ["Low", "Medium", "High", "Critical"];

export default function Rules() {
  const [rules, setRules] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getRules()
      .then(setRules)
      .catch((err) => setError(err.message));
  }, []);

  function replaceRule(updated) {
    setRules((current) => current.map((r) => (r.id === updated.id ? updated : r)));
  }

  return (
    <div>
      <h1 className="page-title">Detection Rules</h1>
      <p className="page-subtitle">
        Tune thresholds and review each rule's limitations. Changes apply to logs uploaded after saving.
      </p>

      <div className="mt-6 space-y-6">
        <ErrorBanner message={error} />
        {!rules && !error && <Spinner />}
        {rules?.map((rule) => (
          <RuleCard key={rule.id} rule={rule} onSaved={replaceRule} />
        ))}
      </div>
    </div>
  );
}

function RuleCard({ rule, onSaved }) {
  const [form, setForm] = useState(() => pickSettings(rule));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null); // { type: "ok" | "error", text }

  const dirty = JSON.stringify(form) !== JSON.stringify(pickSettings(rule));

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
    setMessage(null);
  }

  async function save() {
    setSaving(true);
    setMessage(null);
    const changes = { enabled: form.enabled, severity: form.severity };
    if (rule.uses_threshold) changes.threshold = Number(form.threshold);
    if (rule.uses_window) changes.window_minutes = Number(form.window_minutes);
    try {
      const updated = await updateRule(rule.id, changes);
      onSaved(updated);
      setForm(pickSettings(updated));
      setMessage({ type: "ok", text: "Saved. New settings apply to logs uploaded from now on." });
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card" data-testid={`rule-${rule.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-cyan-300">{rule.id}</span>
            <h2 className="text-lg font-semibold text-slate-100">{rule.name}</h2>
            <SeverityBadge severity={rule.severity} />
            {!rule.enabled && <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">Disabled</span>}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {rule.category} · MITRE ATT&amp;CK {rule.mitre_technique} · updated {formatDateTime(rule.updated_at)}
          </p>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            className="h-4 w-4 accent-cyan-500"
            checked={form.enabled}
            onChange={(e) => update("enabled", e.target.checked)}
          />
          Enabled
        </label>
      </div>

      <p className="mt-3 text-sm text-slate-300">{rule.description}</p>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label className="label" htmlFor={`${rule.id}-severity`}>
            {rule.id === "R004" ? "Base severity" : "Severity"}
          </label>
          <select id={`${rule.id}-severity`} className="input" value={form.severity} onChange={(e) => update("severity", e.target.value)}>
            {SEVERITIES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        {rule.uses_threshold && (
          <div>
            <label className="label" htmlFor={`${rule.id}-threshold`}>Threshold (failures)</label>
            <input
              id={`${rule.id}-threshold`}
              type="number"
              min="1"
              max="1000"
              className="input"
              value={form.threshold}
              onChange={(e) => update("threshold", e.target.value)}
            />
          </div>
        )}
        {rule.uses_window && (
          <div>
            <label className="label" htmlFor={`${rule.id}-window`}>Time window (minutes)</label>
            <input
              id={`${rule.id}-window`}
              type="number"
              min="1"
              max="1440"
              className="input"
              value={form.window_minutes}
              onChange={(e) => update("window_minutes", e.target.value)}
            />
          </div>
        )}
        {!rule.uses_threshold && (
          <p className="self-end text-xs text-slate-500 sm:col-span-2">
            This rule alerts on every matching event, so it has no threshold or time window.
            {rule.id === "R004" && " Severity is raised to High when the service path is in Temp, AppData or Users\\Public."}
          </p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" className="btn-primary" onClick={save} disabled={!dirty || saving}>
          {saving ? "Saving..." : "Save changes"}
        </button>
        {message && (
          <span className={`text-sm ${message.type === "ok" ? "text-emerald-300" : "text-rose-300"}`}>{message.text}</span>
        )}
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 border-t border-slate-800 pt-4 md:grid-cols-2">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-amber-300/90">Limitations</h3>
          <p className="mt-1 text-sm text-slate-400">{rule.limitations}</p>
        </div>
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-amber-300/90">Possible false positives</h3>
          <p className="mt-1 text-sm text-slate-400">{rule.false_positives}</p>
        </div>
      </div>
    </section>
  );
}

function pickSettings(rule) {
  return {
    enabled: rule.enabled,
    severity: rule.severity,
    threshold: String(rule.threshold),
    window_minutes: String(rule.window_minutes),
  };
}
