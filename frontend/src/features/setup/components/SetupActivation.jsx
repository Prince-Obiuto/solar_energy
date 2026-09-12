import { ArrowPathIcon, CheckBadgeIcon } from "@heroicons/react/24/outline";
import { useState } from "react";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import useSetupStore from "../store/setup.store";
import { setupRequestError } from "../utils/setupErrors";

export default function SetupActivation() {
  const refreshStatus = useSetupStore((state) => state.refreshStatus);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState(null);

  const checkActivation = async () => {
    setChecking(true);
    setError(null);
    try {
      await refreshStatus({ force: true });
    } catch (caughtError) {
      setError(setupRequestError(caughtError, "Activation status could not be checked."));
    } finally {
      setChecking(false);
    }
  };

  return (
    <main className="grid min-h-screen place-items-center bg-gray-50 p-4 sm:p-6">
      <div className="w-full max-w-2xl space-y-5">
        <Card className="text-center" padding="p-7 sm:p-10">
          <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-emerald-100 text-emerald-700"><CheckBadgeIcon aria-hidden="true" className="size-8" /></div>
          <p className="mt-5 text-sm font-semibold text-emerald-600">Solar Energy Management System</p>
          <h1 className="mt-1 text-3xl font-bold text-gray-950">Setup complete</h1>
          <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-gray-600">Configuration was saved securely and first-time setup is now permanently locked.</p>
          <div aria-live="polite" className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-left">
            <p className="font-semibold text-amber-900">Waiting for service activation</p>
            <p className="mt-1 text-sm text-amber-800">The backend must restart once to construct the production runtime from the saved configuration. During local development, restart the backend service and then check activation.</p>
          </div>
          {error && <div className="mt-5"><Alert role="alert" tone="error">{error}</Alert></div>}
          <Button className="mt-6" disabled={checking} onClick={checkActivation}>
            <ArrowPathIcon aria-hidden="true" className={`size-4 ${checking ? "animate-spin" : ""}`} />
            {checking ? "Checking activation…" : "Check activation"}
          </Button>
        </Card>
        <p className="text-center text-xs text-gray-500">Normal sign-in becomes available after runtime activation succeeds.</p>
      </div>
    </main>
  );
}
