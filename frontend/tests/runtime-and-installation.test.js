import test from "node:test";
import assert from "node:assert/strict";

import { completedSetupDestination, installationState } from "../src/app/router/installationState.js";
import { formatRuntimeMinutes } from "../src/utils/formatters.js";
import { getApiBaseUrl } from "../src/services/http/axiosClient.js";
import { getEnergyWebSocketUrl } from "../src/services/realtime/energySocket.js";


test("battery runtime formats hours, minutes, zero and unavailable distinctly", () => {
  assert.equal(formatRuntimeMinutes(222), "3 h 42 min");
  assert.equal(formatRuntimeMinutes(15), "15 min");
  assert.equal(formatRuntimeMinutes(0), "0 min");
  assert.equal(formatRuntimeMinutes(null), "--");
  assert.equal(formatRuntimeMinutes(-1), "--");
});


test("only explicit incomplete status opens setup", () => {
  assert.equal(installationState("success", { setup_completed: false, setup_required: true }), "setup");
  assert.equal(installationState("success", { setup_completed: true, setup_required: false }), "application");
  assert.equal(installationState("success", { setup_completed: true, setup_required: false, activation_required: true }), "application");
  assert.equal(installationState("success", { setup_required: true }), "error");
  assert.equal(installationState("success", null), "error");
  for (const failure of ["error", "idle", "loading"]) {
    assert.notEqual(installationState(failure, { setup_completed: false, setup_required: true }), "setup");
  }
});


test("completed setup routes authenticated users to dashboard and others to login", () => {
  assert.equal(completedSetupDestination("authenticated"), "dashboard");
  assert.equal(completedSetupDestination("anonymous"), "login");
  assert.equal(completedSetupDestination("loading"), "loading");
});


test("direct IP and canonical hostname retain their own WebSocket origin", () => {
  assert.equal(getApiBaseUrl(), "/api/v1");
  assert.equal(
    getEnergyWebSocketUrl({ protocol: "https:", host: "10.10.10.6" }),
    "wss://10.10.10.6/api/v1/ws/energy",
  );
  assert.equal(
    getEnergyWebSocketUrl({ protocol: "https:", host: "solar-energy.ift.internal" }),
    "wss://solar-energy.ift.internal/api/v1/ws/energy",
  );
});
