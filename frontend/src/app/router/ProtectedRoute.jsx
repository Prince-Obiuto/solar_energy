import { Navigate, Outlet } from "react-router-dom";

import Loader from "../../components/ui/Loader";
import { useAuth } from "../providers/AuthContext";

export default function ProtectedRoute() {
  const { status } = useAuth();
  if (status === "loading") return <div className="grid min-h-screen place-items-center"><Loader label="Checking session…" /></div>;
  if (status !== "authenticated") return <Navigate replace to="/login" />;
  return <Outlet />;
}
