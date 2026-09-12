import { useCallback, useEffect, useMemo } from "react";

import useSetupStore from "../store/setup.store";

const STEP_BY_BACKEND = {
  administrator: "administrator",
  beve: "inverter",
  tuya: "breakers",
  devices: "breakers",
  confirm: "review",
};

export default function useSetupWizard() {
  const status = useSetupStore((state) => state.status);
  const requestedStep = useSetupStore((state) => state.requestedStep);
  const setRequestedStep = useSetupStore((state) => state.setRequestedStep);
  const refreshStatus = useSetupStore((state) => state.refreshStatus);

  const canonicalStep = STEP_BY_BACKEND[status?.next_step] || "administrator";
  const allowedSteps = useMemo(() => {
    const steps = [];
    if (status?.admin_configured) steps.push("administrator");
    if (status?.beve_configured) steps.push("inverter");
    if (status?.tuya_configured || status?.devices_verified) steps.push("breakers");
    steps.push(canonicalStep);
    return new Set(steps);
  }, [canonicalStep, status]);
  const currentStep = requestedStep && allowedSteps.has(requestedStep)
    ? requestedStep
    : canonicalStep;

  useEffect(() => {
    if (requestedStep && !allowedSteps.has(requestedStep)) setRequestedStep(null);
  }, [allowedSteps, requestedStep, setRequestedStep]);

  const advanceFrom = useCallback(async () => {
    const nextStatus = await refreshStatus({ force: true });
    setRequestedStep(STEP_BY_BACKEND[nextStatus?.next_step] || null);
    return nextStatus;
  }, [refreshStatus, setRequestedStep]);

  return {
    allowedSteps,
    canonicalStep,
    currentStep,
    navigateTo: setRequestedStep,
    advanceFrom,
  };
}
