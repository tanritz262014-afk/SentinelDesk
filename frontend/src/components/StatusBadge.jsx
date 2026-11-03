// One badge for alert statuses, alert verdicts and incident statuses.
const styles = {
  // alert status
  New: "bg-cyan-500/10 text-cyan-300 ring-cyan-500/30",
  "In Progress": "bg-indigo-500/10 text-indigo-300 ring-indigo-500/30",
  Closed: "bg-slate-700/40 text-slate-300 ring-slate-600",
  // alert verdict
  Suspected: "bg-amber-500/10 text-amber-300 ring-amber-500/30",
  Confirmed: "bg-rose-500/15 text-rose-300 ring-rose-500/40",
  "False Positive": "bg-slate-700/40 text-slate-300 ring-slate-600",
  Benign: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
  // incident status
  Investigating: "bg-indigo-500/10 text-indigo-300 ring-indigo-500/30",
  Escalated: "bg-orange-500/10 text-orange-300 ring-orange-500/30",
  Resolved: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
};

export default function StatusBadge({ value }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${styles[value] || "bg-slate-800 text-slate-300 ring-slate-700"}`}>
      {value}
    </span>
  );
}
