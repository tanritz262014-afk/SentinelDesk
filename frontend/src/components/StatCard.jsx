import { Link } from "react-router-dom";

// A small summary box for the dashboard (e.g. "Critical Alerts: 3").
const accents = {
  cyan: "text-cyan-300",
  rose: "text-rose-400",
  amber: "text-amber-300",
  emerald: "text-emerald-300",
};

export default function StatCard({ label, value, hint, accent = "cyan", to }) {
  const body = (
    <>
      <p className="text-xs font-medium uppercase tracking-wider text-slate-400">{label}</p>
      <p className={`mt-2 text-3xl font-semibold tabular-nums ${accents[accent]}`}>{value ?? "—"}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </>
  );
  if (to) {
    return (
      <Link to={to} className="card block transition-colors hover:border-slate-600">
        {body}
      </Link>
    );
  }
  return <div className="card">{body}</div>;
}
