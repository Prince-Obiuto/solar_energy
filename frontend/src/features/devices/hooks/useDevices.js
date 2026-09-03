import { useCallback, useEffect, useState } from "react";

import { getDevices } from "../services/device.service";
import { subscribeWithCoalescedRefresh } from "../../../services/realtime/energySocket";

export default function useDevices() {
  const [devices, setDevices] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try { setDevices(await getDevices()); setError(null); }
    catch (caughtError) { setError(caughtError instanceof Error ? caughtError : new Error("Unable to load devices.")); }
    finally { setLoading(false); }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => subscribeWithCoalescedRefresh(
    (message) => message.type === "device.online" || message.type === "device.offline",
    refresh,
  ), [refresh]);
  return { devices, error, loading, refresh };
}
