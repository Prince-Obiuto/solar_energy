import { useCallback, useEffect, useMemo, useState } from "react";

import axiosClient from "../../services/http/axiosClient";
import { stopEnergySocket } from "../../services/realtime/energySocket";
import { AuthContext } from "./AuthContext";

export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");

  const refresh = useCallback(async () => {
    try {
      const { data } = await axiosClient.get("/auth/me");
      setUser(data);
      setStatus("authenticated");
      return data;
    } catch {
      setUser(null);
      setStatus("anonymous");
      return null;
    }
  }, []);

  // Initial authentication is synchronization with the server session.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    const handleUnauthorized = () => { setUser(null); setStatus("anonymous"); stopEnergySocket(); };
    window.addEventListener("energy-auth-expired", handleUnauthorized);
    return () => window.removeEventListener("energy-auth-expired", handleUnauthorized);
  }, []);

  const login = useCallback(async (email, password) => {
    await axiosClient.post("/auth/login", { email, password });
    return refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    try { await axiosClient.post("/auth/logout"); } finally {
      stopEnergySocket();
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  const value = useMemo(() => ({ user, status, login, logout, refresh }), [user, status, login, logout, refresh]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
