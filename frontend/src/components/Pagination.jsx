export default function Pagination({ total, limit, offset, onChange }) {
  if (total <= limit) return null;
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-slate-400">
      <span>
        {from}–{to} of {total}
      </span>
      <div className="flex gap-2">
        <button type="button" className="btn-secondary px-3 py-1" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          Previous
        </button>
        <button type="button" className="btn-secondary px-3 py-1" disabled={to >= total} onClick={() => onChange(offset + limit)}>
          Next
        </button>
      </div>
    </div>
  );
}
