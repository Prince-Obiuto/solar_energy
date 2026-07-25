import { BrowserRouter, Routes, Route } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import Energy from "./pages/Energy";
import Areas from "./pages/Areas";
import Devices from "./pages/Devices";
// import Reports from "./pages/Reports";
import Logs from "./pages/Logs";
// import Settings from "./pages/Settings";

export default function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/energy" element={<Energy />} />
        <Route path="/areas" element={<Areas />} />
        <Route path="/devices" element={<Devices />} />
        {/* <Route path="/reports" element={<Reports />} /> */}
        <Route path="/logs" element={<Logs />} />
        {/* <Route path="/settings" element={<Settings />} /> */}
      </Routes>
    </BrowserRouter>
  );
}