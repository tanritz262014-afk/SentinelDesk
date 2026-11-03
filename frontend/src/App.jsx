import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import LogAnalyzer from "./pages/LogAnalyzer.jsx";
import Alerts from "./pages/Alerts.jsx";
import AlertDetail from "./pages/AlertDetail.jsx";
import Incidents from "./pages/Incidents.jsx";
import IncidentCreate from "./pages/IncidentCreate.jsx";
import IncidentDetail from "./pages/IncidentDetail.jsx";
import Rules from "./pages/Rules.jsx";

// Each <Route> maps a URL to a page. All pages share the same Layout (sidebar + header).
export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/logs" element={<LogAnalyzer />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/alerts/:id" element={<AlertDetail />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/incidents/new" element={<IncidentCreate />} />
        <Route path="/incidents/:id" element={<IncidentDetail />} />
        <Route path="/rules" element={<Rules />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
