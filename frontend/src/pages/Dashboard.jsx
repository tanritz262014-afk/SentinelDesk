import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getDashboardSummary } from "../api/client.js";
import ChartCard from "../components/ChartCard.jsx";
import EmptyState from "../components/EmptyState.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import EventTable from "../components/EventTable.jsx";
import SeverityBadge from "../components/SeverityBadge.jsx";
import Spinner from "../components/Spinner.jsx";
import StatCard from "../components/StatCard.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { getChartColors } from "../utils/colors.js";
import { useTheme } from "../utils/theme.js";
import { formatDateTime } from "../utils/format.js";

const REFRESH_MS = 30000;

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState(null);

  const load = useCallback(() => {
    getDashboardSummary()
      .then((d) => {
        setData(d);
        setError("");
        setUpdatedAt(new Date());
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">SOC Dashboard</h1>
          <p className="page-subtitle">Overview of alerts and incidents across monitored hosts.</p>
        </div>
        {updatedAt && (
          <p className="text-xs text-slate-500">
            Auto-refresh every 30 s · last updated {updatedAt.toLocaleTimeString()}
          </p>
        )}
      </div>

      {error && (
        <div className="mt-6">
          <ErrorBanner message={error} />
        </div>
      )}
      {!data && !error && <Spinner />}

      {data && (
        <>
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Total Alerts" value={data.total_alerts} hint={`${data.open_alerts} not closed`} accent="cyan" to="/alerts" />
            <StatCard label="Critical Alerts" value={data.critical_alerts} hint="Severity = Critical" accent="rose" to="/alerts?severity=Critical" />
            <StatCard label="Open Incidents" value={data.open_incidents} hint="New / Investigating / Escalated" accent="amber" to="/incidents" />
            <StatCard label="Resolved Incidents" value={data.resolved_incidents} hint="Closed cases" accent="emerald" to="/incidents?status=Resolved" />
          </div>

          <VerdictStrip verdicts={data.alerts_by_verdict} totalEvents={data.total_events} />

          {data.total_events === 0 ? (
            <div className="card mt-6">
              <EmptyState
                title="No security events yet."
                hint="Upload backend/sample_data/suspicious_events.json in the Log Analyzer to see the dashboard fill up."
              />
              <div className="mt-4 text-center">
                <Link to="/logs" className="btn-primary">Go to Log Analyzer</Link>
              </div>
            </div>
          ) : (
            <>
              <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
                <ChartCard title="Alerts by severity" subtitle="All alerts, any status" rows={data.alerts_by_severity}>
                  <SeverityChart rows={data.alerts_by_severity} />
                </ChartCard>
                <ChartCard title="Alerts by event category" subtitle="Grouped by the rule that raised the alert" rows={data.alerts_by_category}>
                  {data.alerts_by_category.length ? (
                    <CategoryChart rows={data.alerts_by_category} />
                  ) : (
                    <EmptyState title="No alerts yet." />
                  )}
                </ChartCard>
              </div>

              <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
                <section className="card min-w-0">
                  <div className="flex items-center justify-between">
                    <h2 className="section-title">Recent security events</h2>
                    <span className="text-xs text-slate-500">{data.total_events} stored</span>
                  </div>
                  <div className="mt-3">
                    <EventTable events={data.recent_events} />
                  </div>
                </section>
                <RecentAlerts alerts={data.recent_alerts} />
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

function VerdictStrip({ verdicts, totalEvents }) {
  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-2 text-sm">
      <span className="text-xs uppercase tracking-wider text-slate-500">Alert verdicts</span>
      {verdicts.map((v) => (
        <Link key={v.name} to={`/alerts?verdict=${encodeURIComponent(v.name)}`} className="flex items-center gap-2 hover:opacity-80">
          <StatusBadge value={v.name} />
          <span className="tabular-nums text-slate-200">{v.count}</span>
        </Link>
      ))}
      <span className="ml-auto text-xs text-slate-500">{totalEvents} events analysed</span>
    </div>
  );
}

// Tooltip shown when hovering a bar. Text uses text colors; a small swatch
// carries the series color.
function BarTooltip({ active, payload, colorFor }) {
  if (!active || !payload?.length) return null;
  const { name, count } = payload[0].payload;
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs shadow-xl">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-sm" style={{ background: colorFor(name) }} />
        <span className="text-slate-300">{name}</span>
      </div>
      <p className="mt-1 text-sm font-semibold tabular-nums text-slate-100">
        {count} alert{count === 1 ? "" : "s"}
      </p>
    </div>
  );
}

function axisProps(c) {
  return { stroke: c.axis, tick: { fill: c.tick, fontSize: 12 }, tickLine: false };
}

function SeverityChart({ rows }) {
  const c = getChartColors(useTheme());
  const colorFor = (name) => c.severity[name] || c.accent;
  return (
    <div className="h-64" data-testid="severity-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 20, right: 8, left: -16, bottom: 0 }} barCategoryGap="28%">
          <CartesianGrid vertical={false} stroke={c.grid} />
          <XAxis dataKey="name" {...axisProps(c)} />
          <YAxis allowDecimals={false} {...axisProps(c)} axisLine={false} />
          <Tooltip cursor={{ fill: c.cursor }} content={<BarTooltip colorFor={colorFor} />} />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.name} fill={colorFor(r.name)} />
            ))}
            <LabelList dataKey="count" position="top" fill={c.label} fontSize={12} formatter={(v) => (v ? v : "")} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function CategoryChart({ rows }) {
  const c = getChartColors(useTheme());
  return (
    <div className="h-64" data-testid="category-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 32, left: 8, bottom: 0 }} barCategoryGap="30%">
          <CartesianGrid horizontal={false} stroke={c.grid} />
          <XAxis type="number" allowDecimals={false} {...axisProps(c)} />
          <YAxis type="category" dataKey="name" width={140} {...axisProps(c)} axisLine={false} />
          <Tooltip cursor={{ fill: c.cursor }} content={<BarTooltip colorFor={() => c.accent} />} />
          <Bar dataKey="count" fill={c.accent} radius={[0, 4, 4, 0]} maxBarSize={36} isAnimationActive={false}>
            <LabelList dataKey="count" position="right" fill={c.label} fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function RecentAlerts({ alerts }) {
  return (
    <section className="card h-fit">
      <div className="flex items-center justify-between">
        <h2 className="section-title">Latest alerts</h2>
        <Link to="/alerts" className="text-xs text-cyan-300 hover:underline">View all →</Link>
      </div>
      <ul className="mt-3 space-y-2">
        {alerts.length === 0 && <li className="text-sm text-slate-500">No alerts yet.</li>}
        {alerts.map((a) => (
          <li key={a.id}>
            <Link to={`/alerts/${a.id}`} className="block rounded-lg border border-slate-800 p-3 hover:border-slate-600">
              <div className="flex flex-wrap items-center gap-1.5">
                <SeverityBadge severity={a.severity} />
                <StatusBadge value={a.verdict} />
                <span className="font-mono text-xs text-slate-500">{a.rule_id}</span>
              </div>
              <p className="mt-1.5 text-sm text-slate-200">{a.title}</p>
              <p className="mt-0.5 font-mono text-xs text-slate-500">{formatDateTime(a.last_seen)}</p>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
