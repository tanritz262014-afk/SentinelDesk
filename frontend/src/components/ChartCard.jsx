import { useState } from "react";

// A card that shows a chart, with a "Table" view of the same numbers
// for screen readers, printing, or anyone who prefers exact values.
export default function ChartCard({ title, subtitle, rows, valueLabel = "Count", children }) {
  const [view, setView] = useState("chart");
  return (
    <section className="card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="section-title">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        <div className="flex rounded-lg border border-slate-700 p-0.5 text-xs" role="group" aria-label={`${title} view`}>
          {["chart", "table"].map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => setView(v)}
              className={`rounded-md px-2 py-1 capitalize ${view === v ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:text-slate-200"}`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-4">
        {view === "chart" ? (
          children
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th className="text-right">{valueLabel}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {rows.map((r) => (
                <tr key={r.name}>
                  <td>{r.name}</td>
                  <td className="text-right tabular-nums">{r.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
