export default function Spinner({ label = "Loading..." }) {
  return (
    <div className="flex items-center gap-2 py-6 text-sm text-slate-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-400" />
      {label}
    </div>
  );
}
