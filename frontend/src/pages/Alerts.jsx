import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getAlerts } from "../api/client.js";
import EmptyState from "../components/EmptyState.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import Pagination from "../components/Pagination.jsx";
import SeverityBadge from "../components/SeverityBadge.jsx";
import Spinner from "../components/Spinner.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatDateTime } from "../utils/format.js";

const PAGE_SIZE = 25;
const FILTERS = [
  { key: "severity", label: "Severity", options: ["Low", "Medium", "High", "Critical"] },
  { key: "status", label: "Status", options: ["New", "In Progress", "Closed"] },
  { key: "verdict", label: "Verdict", options: ["Suspected", "Confirmed", "False Positive", "Benign"] },
  { key: "rule_id", label: "Rule", options: ["R001", "R002", "R003", "R004"] },
];

export default function Alerts() {
  // Filters live in the URL, so a filtered view can be bookmarked or linked.
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") || "");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const offset = Number(params.get("offset") || 0);
  const query = Object.fromEntries(params.entries());

  useEffect(() => {
    setError("");
    getAlerts({ ...query, limit: PAGE_SIZE, offset })
      .then(setData)
      .catch((err) => setError(err.message));
  }, [params]);

  function setFilter(key, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("offset");
    setParams(next);
  }

  return (
    <div>
      <h1 className="page-title">Alert Investigation</h1>
      <p className="page-subtitle">Every alert starts as Suspected. Investigate the evidence before choosing a verdict.</p>

      <div className="card mt-6">
        <form
          className="grid grid-cols-1 gap-3 md:grid-cols-6"
          onSubmit={(e) => {
            e.preventDefault();
            setFilter("q", search.trim());
          }}
        >
          <div className="md:col-span-2">
            <label className="label" htmlFor="alert-search">Search</label>
            <input
              id="alert-search"
              className="input"
              placeholder="Title, host, user or IP"
              value={search}
              maxLength={100}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {FILTERS.map((f) => (
            <div key={f.key}>
              <label className="label" htmlFor={`filter-${f.key}`}>{f.label}</label>
              <select id={`filter-${f.key}`} className="input" value={params.get(f.key) || ""} onChange={(e) => setFilter(f.key, e.target.value)}>
                <option value="">All</option>
                {f.options.map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            </div>
          ))}
          <div className="flex gap-2 md:col-span-6">
            <button type="submit" className="btn-primary">Search</button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setSearch("");
                setParams(new URLSearchParams());
              }}
            >
              Reset filters
            </button>
          </div>
        </form>
      </div>

      <div className="card mt-6">
        <ErrorBanner message={error} />
        {!data && !error && <Spinner />}
        {data && data.items.length === 0 && (
          <EmptyState title="No alerts match these filters." hint="Upload logs in the Log Analyzer to generate alerts." />
        )}
        {data && data.items.length > 0 && (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Alert</th>
                    <th>Host / User</th>
                    <th>Source IP</th>
                    <th>Last seen (UTC)</th>
                    <th>Status</th>
                    <th>Verdict</th>
                    <th>Incident</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {data.items.map((a) => (
                    <tr key={a.id}>
                      <td><SeverityBadge severity={a.severity} /></td>
                      <td className="min-w-[14rem]">
                        <Link to={`/alerts/${a.id}`} className="text-slate-100 hover:text-cyan-300 hover:underline">
                          {a.title}
                        </Link>
                        <p className="text-xs text-slate-500">
                          #{a.id} · {a.rule_id} · {a.event_count} event{a.event_count === 1 ? "" : "s"}
                        </p>
                      </td>
                      <td>
                        <span className="block whitespace-nowrap">{a.hostname || "—"}</span>
                        <span className="block whitespace-nowrap text-xs text-slate-400">{a.username || "—"}</span>
                      </td>
                      <td className="whitespace-nowrap font-mono text-xs">{a.source_ip || "—"}</td>
                      <td className="whitespace-nowrap font-mono text-xs">{formatDateTime(a.last_seen).replace(" UTC", "")}</td>
                      <td><StatusBadge value={a.status} /></td>
                      <td><StatusBadge value={a.verdict} /></td>
                      <td>
                        {a.incident_id ? (
                          <Link to={`/incidents/${a.incident_id}`} className="text-cyan-300 hover:underline">#{a.incident_id}</Link>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              total={data.total}
              limit={PAGE_SIZE}
              offset={offset}
              onChange={(next) => {
                const p = new URLSearchParams(params);
                p.set("offset", String(next));
                setParams(p);
              }}
            />
          </>
        )}
      </div>
    </div>
  );
}
