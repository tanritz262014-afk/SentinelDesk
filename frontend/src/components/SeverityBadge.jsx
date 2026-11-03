const styles = {
  Low: "bg-sky-500/10 text-sky-300 ring-sky-500/30",
  Medium: "bg-yellow-500/10 text-yellow-300 ring-yellow-500/30",
  High: "bg-orange-500/10 text-orange-300 ring-orange-500/30",
  Critical: "bg-rose-500/15 text-rose-300 ring-rose-500/40",
};

export default function SeverityBadge({ severity }) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${styles[severity] || "bg-slate-800 text-slate-300 ring-slate-700"}`}>
      {severity}
    </span>
  );
}
