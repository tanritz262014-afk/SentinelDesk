import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getIncidents } from "../api/client.js";
import EmptyState from "../components/EmptyState.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import Pagination from "../components/Pagination.jsx";
import SeverityBadge from "../components/SeverityBadge.jsx";
import Spinner from "../components/Spinner.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatDateTime } from "../utils/format.js";

const PAGE_SIZE = 25;
const FILTERS = [
  { key: "status", label: "Status", options: ["New", "Investigating", "Escalated", "Resolved"] },
  { key: "severity", label: "Severity", options: ["Low", "Medium", "High", "Critical"] },
  { key: "priority", label: "Priority", options: ["P1", "P2", "P3", "P4"] },
];

export default function Incidents() {
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") || "");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const offset = Number(params.get("offset") || 0);

  useEffect(() => {
    setError("");
    getIncidents({ ...Object.fromEntries(params.entries()), limit: PAGE_SIZE, offset })
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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Incident Management</h1>
          <p className="page-subtitle">Track incidents from New to Resolved. Every change is recorded in the timeline.</p>
        </div>
        <Link to="/incidents/new" className="btn-primary">New incident</Link>
      </div>

      <div className="card mt-6">
        <form
          className="grid grid-cols-1 gap-3 md:grid-cols-5"
          onSubmit={(e) => {
            e.preventDefault();
            setFilter("q", search.trim());
          }}
        >
          <div className="md:col-span-2">
            <label className="label" htmlFor="incident-search">Search</label>
            <input id="incident-search" className="input" placeholder="Title, description or assignee" maxLength={100} value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          {FILTERS.map((f) => (
            <div key={f.key}>
              <label className="label" htmlFor={`incident-${f.key}`}>{f.label}</label>
              <select id={`incident-${f.key}`} className="input" value={params.get(f.key) || ""} onChange={(e) => setFilter(f.key, e.target.value)}>
                <option value="">All</option>
                {f.options.map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            </div>
          ))}
          <div className="flex gap-2 md:col-span-5">
            <button type="submit" className="btn-primary">Search</button>
            <button type="button" className="btn-secondary" onClick={() => { setSearch(""); setParams(new URLSearchParams()); }}>
              Reset filters
            </button>
          </div>
        </form>
      </div>

      <div className="card mt-6">
        <ErrorBanner message={error} />
        {!data && !error && <Spinner />}
        {data && data.items.length === 0 && (
          <EmptyState title="No incidents found." hint="Create one from an alert, or with the New incident button." />
        )}
        {data && data.items.length > 0 && (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Severity</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Assigned to</th>
                    <th>Alerts</th>
                    <th>Updated (UTC)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {data.items.map((i) => (
                    <tr key={i.id}>
                      <td className="font-mono text-xs text-slate-500">#{i.id}</td>
                      <td className="min-w-[14rem]">
                        <Link to={`/incidents/${i.id}`} className="text-slate-100 hover:text-cyan-300 hover:underline">{i.title}</Link>
                      </td>
                      <td><SeverityBadge severity={i.severity} /></td>
                      <td className="font-mono">{i.priority}</td>
                      <td><StatusBadge value={i.status} /></td>
                      <td>{i.assigned_to || <span className="text-slate-600">Unassigned</span>}</td>
                      <td>{i.alert_count}</td>
                      <td className="whitespace-nowrap font-mono text-xs">{formatDateTime(i.updated_at).replace(" UTC", "")}</td>
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
