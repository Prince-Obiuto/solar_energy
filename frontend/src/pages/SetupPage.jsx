import { useEffect } from "react";
import { Navigate } from "react-router-dom";

import ErrorState from "../components/ui/ErrorState";
import Loader from "../components/ui/Loader";
import { useAuth } from "../app/providers/AuthContext";
import { APP_ROUTES } from "../app/router/routes";
import { completedSetupDestination } from "../app/router/installationState";
import AdministratorSetupStep from "../features/setup/components/AdministratorSetupStep";
import BeveSetupStep from "../features/setup/components/BeveSetupStep";
import SetupAuthorization from "../features/setup/components/SetupAuthorization";
import SetupActivation from "../features/setup/components/SetupActivation";
import SetupReview from "../features/setup/components/SetupReview";
import SetupShell from "../features/setup/components/SetupShell";
import TuyaSetupStep from "../features/setup/components/TuyaSetupStep";
import useSetupWizard from "../features/setup/hooks/useSetupWizard";
import useSetupStore from "../features/setup/store/setup.store";
import { setupRequestError } from "../features/setup/utils/setupErrors";

export default function SetupPage() {
  const auth = useAuth();
  const status = useSetupStore((state) => state.status);
  const statusState = useSetupStore((state) => state.statusState);
  const statusError = useSetupStore((state) => state.statusError);
  const authorized = useSetupStore((state) => state.authorized);
  const refreshStatus = useSetupStore((state) => state.refreshStatus);
  const resetInMemorySetup = useSetupStore((state) => state.resetInMemorySetup);
  const wizard = useSetupWizard();

  useEffect(() => {
    if (statusState === "idle") refreshStatus().catch(() => undefined);
  }, [refreshStatus, statusState]);

  useEffect(() => {
    if (statusState === "success" && status?.setup_required === false) resetInMemorySetup();
  }, [resetInMemorySetup, status?.setup_required, statusState]);

  if (statusState === "idle" || statusState === "loading") {
    return <div className="grid min-h-screen place-items-center bg-gray-50"><Loader label="Loading setup…" /></div>;
  }
  if (statusState === "error") {
    return (
      <main className="grid min-h-screen place-items-center bg-gray-50 p-4">
        <div className="w-full max-w-xl"><ErrorState description={setupRequestError(statusError, "Installation status could not be loaded.")} onRetry={() => refreshStatus({ force: true }).catch(() => undefined)} title="Unable to load setup" /></div>
      </main>
    );
  }
  if (status?.setup_completed !== true && !(status?.setup_completed === false && status?.setup_required === true)) {
    return <main className="grid min-h-screen place-items-center bg-gray-50 p-4"><div className="w-full max-w-xl"><ErrorState description="The server returned an invalid installation status. Setup remains locked until this is resolved." onRetry={() => refreshStatus({ force: true }).catch(() => undefined)} title="Unable to verify installation" /></div></main>;
  }
  if (status.setup_completed) {
    if (status?.activation_required) return <SetupActivation />;
    const destination = completedSetupDestination(auth.status);
    if (destination === "loading") return <div className="grid min-h-screen place-items-center"><Loader label="Opening application…" /></div>;
    return <Navigate replace to={destination === "dashboard" ? APP_ROUTES.dashboard : APP_ROUTES.login} />;
  }

  const content = !authorized ? (
    <SetupAuthorization
      initializationRequired={status.next_step === "initialize"}
      onRetryStatus={() => refreshStatus({ force: true }).catch(() => undefined)}
    />
  ) : wizard.currentStep === "administrator" ? (
    <AdministratorSetupStep configured={status.admin_configured} onAdvance={wizard.advanceFrom} />
  ) : wizard.currentStep === "inverter" ? (
    <BeveSetupStep configured={status.beve_configured} onAdvance={wizard.advanceFrom} />
  ) : wizard.currentStep === "breakers" ? (
    <TuyaSetupStep configured={status.devices_verified} onAdvance={wizard.advanceFrom} />
  ) : (
    <SetupReview status={status} />
  );

  return (
    <SetupShell
      allowedSteps={authorized ? wizard.allowedSteps : new Set()}
      authorized={authorized}
      currentStep={wizard.currentStep}
      onNavigate={wizard.navigateTo}
      status={status}
    >
      {content}
    </SetupShell>
  );
}
