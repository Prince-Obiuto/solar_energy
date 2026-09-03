import axiosClient from "../../../services/http/axiosClient";
import { TELEMETRY_STALE_AFTER_MS } from "../../../utils/constants";

export async function getDevices() {
  const { data } = await axiosClient.get("/devices");
  return (data.items || []).map((device) => ({
    id: device.id,
    name: device.friendly_name,
    type: device.type,
    icon: device.type === "breaker" ? "breakers" : device.type,
    status: device.connectivity_type === "cloud"
      ? !device.data_status?.available ? "Cloud unavailable" : device.data_status?.stale ? "Source delayed" : "Live"
      : !device.online ? "Offline" : device.last_seen && Date.now() - new Date(device.last_seen).getTime() > TELEMETRY_STALE_AFTER_MS ? "Stale" : "Live",
    online: device.online,
    area: device.area,
    lastSeen: device.last_seen,
    connectivityType: device.connectivity_type,
    dataSource: device.data_source,
    dataStatus: device.data_status,
    relayOn: device.relay_on,
    capabilities: device.capabilities || {},
  }));
}
