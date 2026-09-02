import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../providers/AuthContext";

export default function RoleRoute({ roles }) {
  const { user } = useAuth();
  return roles.includes(user?.role) ? <Outlet /> : <Navigate replace to="/" />;
}
