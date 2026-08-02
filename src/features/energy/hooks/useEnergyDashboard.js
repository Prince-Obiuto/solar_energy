import { useCallback, useEffect } from "react";

import useInterval from "../../../hooks/useInterval";
import { ENERGY_REFRESH_INTERVAL_MS } from "../../../utils/constants";
import { getEnergySummary } from "../services/energy.service";
import useEnergyStore from "../store/energy.store";

export default function useEnergyDashboard() {
  const { data, error, status, setData, setError, setLoading } = useEnergyStore();

  const refresh = useCallback(() => {
    try {
      setLoading();
      setData(getEnergySummary());
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError : new Error("Unexpected energy data error."));
    }
  }, [setData, setError, setLoading]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useInterval(refresh, ENERGY_REFRESH_INTERVAL_MS);

  return { data, error, isLoading: status === "loading" || status === "idle", refresh };
}
