import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import ErrorState from "../../components/ui/ErrorState";
import Loader from "../../components/ui/Loader";
import useSetupStore from "../../features/setup/store/setup.store";
import { setupRequestError } from "../../features/setup/utils/setupErrors";
import { APP_ROUTES } from "./routes";

export default function InstallationGate() {
  const location = useLocation();
  const status = useSetupStore((state) => state.status);
  const statusState = useSetupStore((state) => state.statusState);
  const statusError = useSetupStore((state) => state.statusError);
  const refreshStatus = useSetupStore((state) => state.refreshStatus);

  useEffect(() => {
    if (statusState === "idle") refreshStatus().catch(() => undefined);
  }, [refreshStatus, statusState]);

  if (statusState === "idle" || statusState === "loading") {
    return <div className="grid min-h-screen place-items-center bg-gray-50"><Loader label="Checking installation status…" /></div>;
  }
  if (statusState === "error") {
    return (
      <main className="grid min-h-screen place-items-center bg-gray-50 p-4">
        <div className="w-full max-w-xl">
          <ErrorState
            description={setupRequestError(statusError, "Installation status could not be checked. Normal routes remain locked until the server responds.")}
            onRetry={() => refreshStatus({ force: true }).catch(() => undefined)}
            title="Unable to verify installation"
          />
        </div>
      </main>
    );
  }
  if (status?.setup_required || status?.activation_required) {
    return <Navigate replace state={{ from: location.pathname }} to={APP_ROUTES.setup} />;
  }
  return <Outlet />;
}
