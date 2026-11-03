import { NavLink } from "react-router-dom";

// Simple inline SVG icons (no extra icon library needed)
const icons = {
  dashboard: "M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z",
  logs: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h5",
  alerts: "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01",
  incidents: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v0a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2zM9 12h6M9 16h4",
  rules: "M12 3v3M12 18v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M3 12h3M18 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
};

const navItems = [
  { to: "/", label: "Dashboard", icon: "dashboard" },
  { to: "/logs", label: "Log Analyzer", icon: "logs" },
  { to: "/alerts", label: "Alerts", icon: "alerts" },
  { to: "/incidents", label: "Incidents", icon: "incidents" },
  { to: "/rules", label: "Detection Rules", icon: "rules" },
];

function Icon({ path }) {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

export default function Sidebar() {
  return (
    <aside className="flex w-16 shrink-0 flex-col border-r border-slate-800 bg-slate-900/60 md:w-60">
      <div className="flex items-center gap-2 px-4 py-5">
        <img src="/shield.svg" alt="" className="h-7 w-7" />
        <div className="hidden md:block">
          <p className="font-semibold tracking-wide text-slate-100">SentinelDesk</p>
          <p className="text-[11px] uppercase tracking-widest text-cyan-400/80">Mini SOC</p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            title={item.label}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                isActive
                  ? "bg-cyan-500/10 text-cyan-300 ring-1 ring-inset ring-cyan-500/30"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`
            }
          >
            <Icon path={icons[item.icon]} />
            <span className="hidden md:inline">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <p className="hidden px-4 py-4 text-[11px] text-slate-600 md:block">Demo data only · v1.1.0</p>
    </aside>
  );
}
