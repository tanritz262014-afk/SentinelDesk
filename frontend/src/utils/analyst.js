// Remembers the analyst name typed in note forms (per browser only).
// There is no login in this project, so this is just a convenience label.
const KEY = "sentineldesk.analyst";

export function getAnalystName() {
  try {
    return localStorage.getItem(KEY) || "analyst";
  } catch {
    return "analyst";
  }
}

export function saveAnalystName(name) {
  try {
    localStorage.setItem(KEY, name);
  } catch {
    // storage may be blocked; ignore
  }
}
