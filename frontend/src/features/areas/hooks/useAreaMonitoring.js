import { useCallback, useEffect, useMemo, useState } from "react";

import { getAreas } from "../services/area.service";
import { subscribeWithCoalescedRefresh } from "../../../services/realtime/energySocket";

export default function useAreaMonitoring() {
  const [areas, setAreas] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [view, setView] = useState("cards");

  const refresh = useCallback(async () => {
    try {
      setAreas(await getAreas());
      setError(null);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError : new Error("Unable to load area telemetry."));
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch and subsequent hardware event refreshes are external synchronization.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => subscribeWithCoalescedRefresh(
    (message) => message.type.startsWith("breaker.") || message.type.startsWith("device."),
    refresh,
  ), [refresh]);

  const filteredAreas = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return areas.filter((area) => {
      const matchesQuery = area.name.toLowerCase().includes(normalizedQuery);
      const matchesStatus = status === "all" || area.breakerStatus.toLowerCase() === status;
      return matchesQuery && matchesStatus;
    });
  }, [areas, query, status]);

  return { filteredAreas, query, setQuery, setStatus, setView, status, view, error, loading, refresh };
}
