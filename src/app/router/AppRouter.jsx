import { BrowserRouter, Route, Routes } from "react-router-dom";

import AppLayout from "../../components/layout/AppLayout";
import AreasPage from "../../pages/AreasPage";
import DashboardPage from "../../pages/DashboardPage";
import ControlsPage from "../../pages/ControlsPage";
import DevicesPage from "../../pages/DevicesPage";
import NotFoundPage from "../../pages/NotFoundPage";
import LogsPage from "../../pages/LogsPage";
import ReportsPage from "../../pages/ReportsPage";
import SettingsPage from "../../pages/SettingsPage";
import UsersPage from "../../pages/UsersPage";
import SectionPage from "../../pages/SectionPage";
import { APP_ROUTES } from "./routes";

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path={APP_ROUTES.dashboard} element={<DashboardPage />} />
          <Route path={APP_ROUTES.energy} element={<SectionPage title="Energy" />} />
          <Route path={APP_ROUTES.areas} element={<AreasPage />} />
          <Route path={APP_ROUTES.devices} element={<DevicesPage />} />
          <Route path={APP_ROUTES.controls} element={<ControlsPage />} />
          <Route path={APP_ROUTES.reports} element={<ReportsPage />} />
          <Route path={APP_ROUTES.logs} element={<LogsPage />} />
          <Route path={APP_ROUTES.users} element={<UsersPage />} />
          <Route path={APP_ROUTES.settings} element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
