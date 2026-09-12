const BEVE_MESSAGES = {
  authentication_failed: "BEVE authentication failed. Check the supplied account credentials.",
  device_not_found: "The configured inverter device could not be found.",
  network_error: "The server could not reach the BEVE service.",
  timeout: "The BEVE request timed out. Check Internet connectivity and try again.",
  malformed_response: "The service responded, but the inverter data could not be validated.",
  configuration_invalid: "The inverter configuration is invalid. Check each field and try again.",
  vendor_error: "The BEVE service returned an error. Try again later.",
};

const TUYA_MESSAGES = {
  cloud_authentication_failed: "Tuya Cloud authentication failed. Check the Access ID and Access Secret.",
  cloud_device_fetch_failed: "Tuya Cloud did not return a usable device list.",
  cloud_configuration_invalid: "The Tuya Cloud configuration is invalid.",
  network_error: "The server could not reach Tuya Cloud.",
  timeout: "The Tuya operation timed out. Check connectivity and try again.",
  cloud_malformed_response: "Tuya Cloud returned a device list that could not be validated.",
  scan_timeout: "The local network scan timed out. Confirm the breakers and server are on the same LAN.",
  no_devices_found: "No matching Tuya devices were found on the local network.",
  onboarding_session_invalid: "Your Tuya setup session expired. Re-enter the Tuya Cloud credentials to continue.",
  device_not_on_lan: "A selected breaker is no longer available on the local network.",
  device_id_mismatch: "A selected device no longer matches this setup session.",
  local_connection_failed: "Could not communicate with a selected breaker on the local network.",
  protocol_error: "A selected breaker protocol could not be validated.",
  malformed_response: "A breaker responded, but its data could not be validated.",
  unsupported_device: "A selected device is not compatible with the supported breaker profile.",
  configuration_invalid: "The selected breaker configuration is invalid.",
};

const COMPLETION_MESSAGES = {
  configuration_incomplete: "Complete and verify every setup stage before finalizing.",
  master_key_unavailable: "The secure runtime key is unavailable. Ask the installer to verify the server configuration.",
  beve_configuration_invalid: "The saved inverter configuration could not be validated. Review the inverter setup before finalizing.",
  tuya_configuration_invalid: "The saved smart-breaker configuration could not be validated. Review the breaker setup before finalizing.",
  runtime_configuration_invalid: "The saved runtime configuration could not be validated.",
};

export function setupResultMessage(category, fallback, kind = "tuya") {
  const messages = kind === "beve"
    ? BEVE_MESSAGES
    : kind === "completion" ? COMPLETION_MESSAGES : TUYA_MESSAGES;
  return messages[category] || fallback || "The setup operation could not be completed.";
}

export function setupRequestError(error, fallback = "The setup request could not be completed.") {
  const status = error?.response?.status;
  if (status === 409) return "A device scan is already in progress.";
  if (status === 410) return "Installation setup is no longer available.";
  if (status === 429) return "Too many setup attempts. Wait a moment and try again.";
  if (status === 400) return "The setup request was rejected. Check the current setup step and try again.";
  if (status === 422) return "Check the supplied values and correct any invalid fields.";
  if (!error?.response) return "The server could not be reached. Check the connection and try again.";
  return fallback;
}
