// The API returns UTC times like "2026-10-01T09:15:02". We show them as UTC
// on purpose, so every analyst sees the same time as the original logs.
export function formatDateTime(value) {
  if (!value) return "—";
  return `${String(value).replace("T", " ").slice(0, 19)} UTC`;
}

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
