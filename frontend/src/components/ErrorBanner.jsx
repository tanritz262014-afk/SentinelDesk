export default function ErrorBanner({ message, children }) {
  if (!message) return null;
  return (
    <div role="alert" className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
      <p className="font-medium">{message}</p>
      {children}
    </div>
  );
}
