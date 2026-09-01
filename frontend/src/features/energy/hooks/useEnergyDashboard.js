import { useCallback, useEffect, useState } from "react";

import useInterval from "../../../hooks/useInterval";
import { ENERGY_REFRESH_INTERVAL_MS } from "../../../utils/constants";
import { TELEMETRY_STALE_AFTER_MS } from "../../../utils/constants";
import { subscribeConnectionStatus, subscribeEnergyEvents } from "../../../services/realtime/energySocket";
import { getEnergySummary } from "../services/energy.service";
import useEnergyStore from "../store/energy.store";

export default function useEnergyDashboard() {
  const { data, error, status, setData, setError, setLoading } = useEnergyStore();
  const [stale, setStale] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setLoading();
      setData(await getEnergySummary());
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError : new Error("Unexpected energy data error."));
    }
  }, [setData, setError, setLoading]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useInterval(refresh, ENERGY_REFRESH_INTERVAL_MS);

  useEffect(() => subscribeEnergyEvents((message) => {
    if (["energy.update", "breaker.telemetry", "breaker.status", "device.online", "device.offline"].includes(message.type)) refresh();
  }), [refresh]);

  useEffect(() => subscribeConnectionStatus((connectionStatus) => useEnergyStore.setState({ connectionStatus })), []);

  useEffect(() => {
    if (!data?.capturedAt) return undefined;
    const staleAt = new Date(data.capturedAt).getTime() + TELEMETRY_STALE_AFTER_MS;
    const delay = staleAt - Date.now();
    const currentTimer = delay > 0 ? window.setTimeout(() => setStale(false), 0) : null;
    const timer = window.setTimeout(() => setStale(true), Math.max(0, delay));
    return () => { window.clearTimeout(timer); window.clearTimeout(currentTimer); };
  }, [data?.capturedAt]);

  return { data, error, isLoading: status === "loading" || status === "idle", refresh, stale };
}
