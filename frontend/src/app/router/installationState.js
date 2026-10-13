export function installationState(statusState, status) {
  if (statusState === "idle" || statusState === "loading") return "loading";
  if (statusState === "error") return "error";
  if (statusState !== "success") return "error";
  if (status?.setup_completed === false && status?.setup_required === true) return "setup";
  if (status?.setup_completed === true && status?.setup_required === false) return "application";
  return "error";
}

export function completedSetupDestination(authStatus) {
  if (authStatus === "loading") return "loading";
  return authStatus === "authenticated" ? "dashboard" : "login";
}
