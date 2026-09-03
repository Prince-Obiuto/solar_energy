import { useCallback, useEffect, useState } from "react";

import { getControllableBreakers } from "../services/control.service";
import { subscribeWithCoalescedRefresh } from "../../../services/realtime/energySocket";

export default function useControlCenter() {
  const [breakers, setBreakers] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setBreakers(await getControllableBreakers());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error("Unable to load breaker controls."));
    } finally {
      setLoading(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => subscribeWithCoalescedRefresh(
    (message) => message.type.startsWith("breaker.") || message.type.startsWith("device."),
    refresh,
  ), [refresh]);

  return { breakers, error, loading, refresh };
}
