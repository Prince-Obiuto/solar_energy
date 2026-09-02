import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import Alert from "../components/ui/Alert";
import Loader from "../components/ui/Loader";
import { useAuth } from "../app/providers/AuthContext";

export default function LoginPage() {
  const { login, status } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "loading") return <div className="grid min-h-screen place-items-center"><Loader label="Checking session…" /></div>;
  if (status === "authenticated") return <Navigate replace to="/" />;

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      navigate(location.state?.from || "/", { replace: true });
    } catch (caughtError) {
      const detail = caughtError.response?.data?.detail;
      setError(detail || "Unable to sign in. Check your credentials and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="grid min-h-screen place-items-center bg-gray-950 p-4">
      <form className="w-full max-w-md space-y-5 rounded-2xl bg-white p-7 shadow-xl" onSubmit={submit}>
        <div><p className="text-sm font-semibold text-emerald-600">Energy Management System</p><h1 className="mt-1 text-2xl font-bold text-gray-950">Sign in</h1><p className="mt-2 text-sm text-gray-500">Use your department account to access monitoring data.</p></div>
        {error && <Alert tone="danger">{error}</Alert>}
        <label className="block text-sm font-medium text-gray-700">Email<input autoComplete="username" className="mt-1.5 block w-full rounded-lg border border-gray-200 px-3 py-2" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} /></label>
        <label className="block text-sm font-medium text-gray-700">Password<input autoComplete="current-password" className="mt-1.5 block w-full rounded-lg border border-gray-200 px-3 py-2" onChange={(event) => setPassword(event.target.value)} required type="password" value={password} /></label>
        <button className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 font-semibold text-white hover:bg-emerald-700 disabled:bg-gray-300" disabled={submitting} type="submit">{submitting ? "Signing in…" : "Sign in"}</button>
      </form>
    </main>
  );
}
