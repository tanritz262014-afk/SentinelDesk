import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import { getHealth } from "../api/client.js";

const HEALTH_POLL_MS = 15000;

// Shared page frame: sidebar on the left, header on top, current page below.
export default function Layout() {
  const [health, setHealth] = useState({ state: "checking", detail: "Checking backend..." });

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const data = await getHealth();
        if (!cancelled) setHealth({ state: "online", detail: `${data.rules_loaded} detection rules loaded` });
      } catch (err) {
        if (!cancelled) setHealth({ state: "offline", detail: err.message });
      }
    }

    check();
    const id = setInterval(check, HEALTH_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-slate-800 bg-slate-950/80 px-6 py-3">
          <p className="truncate text-sm text-slate-400">
            Security Operations Center <span className="text-slate-600">/</span> Analyst Console
          </p>
          <div className="flex items-center gap-2">
            <BackendStatus health={health} />
            <ThemeToggle />
          </div>
        </header>
        <main className="flex-1 overflow-x-hidden p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function BackendStatus({ health }) {
  const styles = {
    online: { dot: "bg-emerald-400", text: "text-emerald-300", label: "Backend Online" },
    offline: { dot: "bg-rose-500", text: "text-rose-300", label: "Backend Offline" },
    checking: { dot: "bg-slate-500 animate-pulse", text: "text-slate-400", label: "Checking..." },
  }[health.state];

  return (
    <div
      title={health.detail}
      className="flex shrink-0 items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs"
    >
      <span className={`h-2 w-2 rounded-full ${styles.dot}`} />
      <span className={styles.text}>{styles.label}</span>
    </div>
  );
}
