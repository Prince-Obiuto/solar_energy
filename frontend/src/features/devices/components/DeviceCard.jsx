import Card from "../../../components/ui/Card";
import StatusChip from "../../../components/ui/StatusChip";
import DeviceIcon from "./DeviceIcon";
import DeviceMetric from "./DeviceMetric";
import { formatRelativeTime } from "../../../utils/formatters";

export default function DeviceCard({ device }) {
  const capabilities = Object.entries(device.capabilities).filter(([, supported]) => supported).map(([name]) => name.replaceAll("_", " "));

  return (
    <Card padding="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <DeviceIcon type={device.icon} />
          <div>
            <h3 className="font-semibold text-gray-900">{device.name}</h3>
            <p className="mt-0.5 text-xs text-gray-500">Last updated {formatRelativeTime(device.dataStatus?.last_successful_update || device.lastSeen)}</p>
          </div>
        </div>
        <StatusChip status={device.status} />
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4">
        <DeviceMetric label="Type" value={device.type || "N/A"} />
        <DeviceMetric label="Area" value={device.area || "N/A"} />
        <DeviceMetric label="Connectivity" value={device.connectivityType || "N/A"} />
        <DeviceMetric label="Data source" value={device.dataSource || "N/A"} />
        {device.type === "breaker" && <DeviceMetric label="Relay" value={device.relayOn == null ? "N/A" : device.relayOn ? "ON" : "OFF"} />}
      </dl>
      <div className="mt-5 rounded-lg bg-gray-50 p-3">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-gray-600">Supported capabilities</span>
          <span className="font-semibold text-gray-800">{capabilities.length}</span>
        </div>
        <p className="mt-2 text-xs capitalize text-gray-600">{capabilities.join(", ") || "None reported"}</p>
      </div>
    </Card>
  );
}
