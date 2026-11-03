import { useEffect, useState } from "react";

// The theme is stored as data-theme="dark" | "light" on <html>.
// index.html sets it before React starts (saved choice, else the OS setting),
// so the page never flashes the wrong colors.
const KEY = "sentineldesk.theme";

export function getTheme() {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // storage may be blocked (private mode); the theme still applies for this visit
  }
}

/** React hook: the current theme, updated whenever it changes. */
export function useTheme() {
  const [theme, setThemeState] = useState(getTheme);
  useEffect(() => {
    const observer = new MutationObserver(() => setThemeState(getTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
  return theme;
}
