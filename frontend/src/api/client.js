// Small wrapper around fetch() so every page handles errors the same way.

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

const DEFAULT_TIMEOUT_MS = 10000;

export class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message);
    this.name = "ApiError";
    this.status = status; // 0 means the server could not be reached
    this.data = data; // full error body, e.g. { detail, errors: [...] }
  }
}

async function send(path, { method = "GET", body, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const options = { method, signal: controller.signal, headers: {} };
  if (body instanceof FormData) {
    options.body = body; // the browser sets the multipart Content-Type itself
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, options);
  } catch (err) {
    if (err.name === "AbortError") {
      throw new ApiError("The request timed out. Is the backend running?");
    }
    throw new ApiError("Cannot reach the backend. Start it with: uvicorn app.main:app --reload");
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    const isJson = response.headers.get("content-type")?.includes("application/json");
    const data = isJson ? await response.json() : null;
    throw new ApiError(formatErrorDetail(data?.detail) || `Request failed (HTTP ${response.status})`, response.status, data);
  }
  return response;
}

/** Call the backend and return the parsed JSON body. Throws ApiError on failure. */
export async function apiRequest(path, options) {
  const response = await send(path, options);
  return response.status === 204 ? null : response.json();
}

// FastAPI returns errors as a string, a list of validation problems, or an object.
function formatErrorDetail(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc.filter((p) => p !== "body").join(".") : "";
        return field ? `${field}: ${d.msg}` : d.msg || JSON.stringify(d);
      })
      .join("; ");
  }
  return JSON.stringify(detail);
}

/** Download a file from the API and save it in the browser. */
export async function downloadFile(path, fallbackName) {
  const response = await send(path, { timeoutMs: 20000 });
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = match ? match[1] : fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Build a query string, skipping empty values. */
export function toQuery(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

// ----- Endpoints -----
export const getHealth = () => apiRequest("/api/health", { timeoutMs: 5000 });

export function uploadLog(file) {
  const form = new FormData();
  form.append("file", file);
  return apiRequest("/api/logs/upload", { method: "POST", body: form, timeoutMs: 60000 });
}
export const getUploads = () => apiRequest("/api/logs/uploads");
export const getEvents = (params = {}) => apiRequest(`/api/events${toQuery(params)}`);

export const getRules = () => apiRequest("/api/rules");
export const updateRule = (id, changes) => apiRequest(`/api/rules/${id}`, { method: "PUT", body: changes });

export const getAlerts = (params = {}) => apiRequest(`/api/alerts${toQuery(params)}`);
export const getAlert = (id) => apiRequest(`/api/alerts/${id}`);
export const getRelatedEvents = (id) => apiRequest(`/api/alerts/${id}/related`);
export const addAlertNote = (id, note, author) =>
  apiRequest(`/api/alerts/${id}/notes`, { method: "POST", body: { note, author } });
export const updateAlert = (id, changes) => apiRequest(`/api/alerts/${id}`, { method: "PATCH", body: changes });

export const getIncidents = (params = {}) => apiRequest(`/api/incidents${toQuery(params)}`);
export const getIncident = (id) => apiRequest(`/api/incidents/${id}`);
export const createIncident = (payload) => apiRequest("/api/incidents", { method: "POST", body: payload });
export const updateIncident = (id, changes) => apiRequest(`/api/incidents/${id}`, { method: "PATCH", body: changes });
export const addIncidentNote = (id, note, author) =>
  apiRequest(`/api/incidents/${id}/notes`, { method: "POST", body: { note, author } });
export const linkIncidentAlerts = (id, alertIds, author) =>
  apiRequest(`/api/incidents/${id}/alerts`, { method: "POST", body: { alert_ids: alertIds, author } });
export const downloadIncidentReport = (id, format) =>
  downloadFile(`/api/incidents/${id}/report?format=${format}`, `incident-${id}-report.${format === "json" ? "json" : "md"}`);

export const getDashboardSummary = () => apiRequest("/api/dashboard/summary");
