import { Fragment, useState } from "react";
import { formatDateTime } from "../utils/format.js";

// Table of security events. When events include raw_data, each row can be
// expanded to show the original log row. It is displayed as plain text
// inside <pre>, never interpreted as HTML or executed.
export default function EventTable({ events, showRaw = false }) {
  const [open, setOpen] = useState({});

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Time (UTC)</th>
            <th>Event</th>
            <th>Host / User</th>
            <th>Source IP</th>
            <th>Details</th>
            {showRaw && <th />}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {events.map((e) => (
            <Fragment key={e.id}>
              <tr>
                <td className="whitespace-nowrap font-mono text-xs">{formatDateTime(e.timestamp).replace(" UTC", "")}</td>
                <td>
                  <span className="font-mono text-cyan-300">{e.event_id}</span>
                  <span className="block text-xs text-slate-500">{e.event_category}</span>
                </td>
                <td>
                  <span className="block whitespace-nowrap">{e.hostname || "—"}</span>
                  <span className="block whitespace-nowrap text-xs text-slate-400">{e.username || "—"}</span>
                </td>
                <td className="whitespace-nowrap font-mono text-xs">{e.source_ip || "—"}</td>
                <td className="min-w-[10rem] text-xs text-slate-400">
                  {e.service_name ? (
                    <span className="break-all">
                      {e.service_name}: <span className="font-mono">{e.service_path}</span>
                    </span>
                  ) : (
                    <>
                      {e.event_description}
                      {e.logon_type && <span className="text-slate-500"> · logon type {e.logon_type}</span>}
                    </>
                  )}
                </td>
                {showRaw && (
                  <td>
                    <button type="button" className="text-xs text-cyan-300 hover:underline" onClick={() => setOpen((o) => ({ ...o, [e.id]: !o[e.id] }))}>
                      {open[e.id] ? "Hide raw" : "Raw"}
                    </button>
                  </td>
                )}
              </tr>
              {showRaw && open[e.id] && (
                <tr>
                  <td colSpan={6} className="bg-slate-950">
                    <pre className="overflow-x-auto whitespace-pre-wrap break-all font-mono text-xs text-slate-300">
                      {JSON.stringify(e.raw_data, null, 2)}
                    </pre>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
