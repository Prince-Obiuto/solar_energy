import axiosClient from "../../../services/http/axiosClient";

const LONG_REQUEST = { timeout: 45_000 };
const LAN_SCAN_REQUEST = { timeout: 120_000 };
const DEVICE_VERIFICATION_REQUEST = { timeout: 180_000 };

const setupService = {
  async getStatus() {
    const { data } = await axiosClient.get("/setup/status");
    return data;
  },

  async verifySetupCode(setupCode) {
    const { data } = await axiosClient.post("/setup/verify", { setup_code: setupCode });
    return data;
  },

  async createAdministrator(setupCode, administrator) {
    const { data } = await axiosClient.post("/setup/administrator", {
      setup_code: setupCode,
      ...administrator,
    });
    return data;
  },

  async testBeve(setupCode, configuration) {
    const { data } = await axiosClient.post(
      "/setup/beve/test",
      { setup_code: setupCode, ...configuration },
      LONG_REQUEST,
    );
    return data;
  },

  async configureBeve(setupCode, configuration) {
    const { data } = await axiosClient.post(
      "/setup/beve",
      { setup_code: setupCode, ...configuration },
      LONG_REQUEST,
    );
    return data;
  },

  async configureTuyaCloud(setupCode, configuration) {
    const { data } = await axiosClient.post(
      "/setup/tuya/cloud",
      { setup_code: setupCode, ...configuration },
      LONG_REQUEST,
    );
    return data;
  },

  async scanTuyaLan(setupCode, onboardingSession) {
    const { data } = await axiosClient.post(
      "/setup/tuya/scan",
      { setup_code: setupCode, onboarding_session: onboardingSession },
      LAN_SCAN_REQUEST,
    );
    return data;
  },

  async configureTuyaDevices(setupCode, onboardingSession, devices) {
    const { data } = await axiosClient.post(
      "/setup/tuya/devices",
      {
        setup_code: setupCode,
        onboarding_session: onboardingSession,
        devices,
      },
      DEVICE_VERIFICATION_REQUEST,
    );
    return data;
  },

  async getTuyaConfigurationStatus(setupCode) {
    const { data } = await axiosClient.post("/setup/tuya/status", {
      setup_code: setupCode,
    });
    return data;
  },
};

export default setupService;
