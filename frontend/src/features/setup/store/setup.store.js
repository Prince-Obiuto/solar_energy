import { create } from "zustand";

import setupService from "../services/setup.service";

let statusRequest = null;

const useSetupStore = create((set) => ({
  status: null,
  statusState: "idle",
  statusError: null,
  setupCode: null,
  authorized: false,
  requestedStep: null,
  restartRequired: false,
  onboardingSession: null,
  candidates: [],
  scanResult: null,
  verificationResults: [],
  tuyaConfiguration: null,

  refreshStatus: async () => {
    if (statusRequest) return statusRequest;
    set({ statusState: "loading", statusError: null });
    statusRequest = setupService.getStatus()
      .then((status) => {
        set({ status, statusState: "success", statusError: null });
        return status;
      })
      .catch((error) => {
        set({ statusState: "error", statusError: error });
        throw error;
      })
      .finally(() => { statusRequest = null; });
    return statusRequest;
  },

  authorize: (setupCode) => set({ setupCode, authorized: true }),
  setRequestedStep: (requestedStep) => set({ requestedStep }),
  requireRestart: () => set({ restartRequired: true }),
  setCloudSession: ({ onboardingSession, candidates }) => set({
    onboardingSession,
    candidates,
    scanResult: null,
    verificationResults: [],
    tuyaConfiguration: null,
  }),
  setScanResult: (scanResult) => set({ scanResult }),
  setVerificationResults: (verificationResults) => set({ verificationResults }),
  setTuyaConfiguration: (tuyaConfiguration) => set({ tuyaConfiguration }),
  markSetupCompleted: (status) => set({
    status,
    statusState: "success",
    setupCode: null,
    authorized: false,
    requestedStep: null,
    onboardingSession: null,
    candidates: [],
    scanResult: null,
    verificationResults: [],
    tuyaConfiguration: null,
    restartRequired: true,
  }),
  expireCloudSession: () => set({
    onboardingSession: null,
    candidates: [],
    scanResult: null,
    verificationResults: [],
  }),
  clearCloudSecrets: () => set({
    onboardingSession: null,
    candidates: [],
    scanResult: null,
  }),
  resetInMemorySetup: () => set({
    setupCode: null,
    authorized: false,
    requestedStep: null,
    onboardingSession: null,
    candidates: [],
    scanResult: null,
    verificationResults: [],
    restartRequired: false,
    tuyaConfiguration: null,
  }),
}));

export default useSetupStore;
