import axiosClient from "../../../services/http/axiosClient";
import { TELEMETRY_STALE_AFTER_MS } from "../../../utils/constants";

export function mapBreakerToArea(breaker) {
  const status = breaker.status || {};
  const electrical = status.electrical || {};
  return {
    id: breaker.id,
    name: breaker.area || breaker.friendly_name,
    friendlyName: breaker.friendly_name,
    breakerStatus: !breaker.online ? "Offline" : status.switch_on == null ? "Unknown" : status.switch_on ? "On" : "Off",
    online: breaker.online,
    currentLoad: electrical.active_power_watts == null ? null : electrical.active_power_watts / 1_000,
    accumulatedEnergy: status.energy?.accumulated_energy ?? null,
    voltage: electrical.voltage_volts ?? null,
    current: electrical.current_amperes ?? null,
    configuration: status.configuration ?? null,
    capabilities: breaker.capabilities || {},
    lastSeen: breaker.last_seen,
    stale: Boolean(breaker.last_seen) && Date.now() - new Date(breaker.last_seen).getTime() > TELEMETRY_STALE_AFTER_MS,
  };
}

export async function getAreas() {
  const { data } = await axiosClient.get("/breakers");
  return (data.items || []).map(mapBreakerToArea);
}
