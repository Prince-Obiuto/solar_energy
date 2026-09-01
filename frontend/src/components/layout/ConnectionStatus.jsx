import { useEffect, useState } from "react";
import { connectEnergySocket, subscribeConnectionStatus } from "../../services/realtime/energySocket";

export default function ConnectionStatus() {
  const [status, setStatus] = useState("connecting");
  useEffect(() => {
    const unsubscribe = subscribeConnectionStatus(setStatus);
    connectEnergySocket();
    return unsubscribe;
  }, []);
  const connected = status === "connected";
  return (
    <div className={`hidden items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium sm:flex ${connected ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
      <span aria-hidden="true" className={`size-2 rounded-full ${connected ? "bg-emerald-500" : "bg-amber-500"}`} />
      {connected ? "Live connection" : status === "reconnecting" ? "Reconnecting…" : "Connecting…"}
    </div>
  );
}
