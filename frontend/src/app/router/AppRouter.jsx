import { lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import AppLayout from "../../components/layout/AppLayout";
import { APP_ROUTES } from "./routes";
import ProtectedRoute from "./ProtectedRoute";
import RoleRoute from "./RoleRoute";

const AreasPage = lazy(() => import("../../pages/AreasPage"));
const ControlsPage = lazy(() => import("../../pages/ControlsPage"));
const DashboardPage = lazy(() => import("../../pages/DashboardPage"));
const DevicesPage = lazy(() => import("../../pages/DevicesPage"));
const EnergyPage = lazy(() => import("../../pages/EnergyPage"));
const LogsPage = lazy(() => import("../../pages/LogsPage"));
const LoginPage = lazy(() => import("../../pages/LoginPage"));
const NotFoundPage = lazy(() => import("../../pages/NotFoundPage"));
const ReportsPage = lazy(() => import("../../pages/ReportsPage"));
const SettingsPage = lazy(() => import("../../pages/SettingsPage"));
const UsersPage = lazy(() => import("../../pages/UsersPage"));

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path={APP_ROUTES.login} element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
          <Route path={APP_ROUTES.dashboard} element={<DashboardPage />} />
          <Route path={APP_ROUTES.energy} element={<EnergyPage />} />
          <Route path={APP_ROUTES.reports} element={<ReportsPage />} />
          <Route element={<RoleRoute roles={["staff", "admin"]} />}>
            <Route path={APP_ROUTES.areas} element={<AreasPage />} />
            <Route path={APP_ROUTES.devices} element={<DevicesPage />} />
          </Route>
          <Route element={<RoleRoute roles={["admin"]} />}>
            <Route path={APP_ROUTES.controls} element={<ControlsPage />} />
            <Route path={APP_ROUTES.logs} element={<LogsPage />} />
            <Route path={APP_ROUTES.users} element={<UsersPage />} />
            <Route path={APP_ROUTES.settings} element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
