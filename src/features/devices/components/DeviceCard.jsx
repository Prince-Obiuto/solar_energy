import Card from "../../../components/ui/Card";
import DeviceActions from "./DeviceActions";
import DeviceIcon from "./DeviceIcon";
import DeviceMetric from "./DeviceMetric";
import DeviceStatus from "./DeviceStatus";

export default function DeviceCard({ device, onAction }) {
  const healthTone = device.health >= 90 ? "bg-emerald-500" : "bg-amber-500";

  return (
    <Card className="border border-gray-100 p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <DeviceIcon type={device.icon} />
          <div>
            <h3 className="font-semibold text-gray-900">{device.name}</h3>
            <p className="mt-0.5 text-xs text-gray-500">Last seen {device.lastSeen}</p>
          </div>
        </div>
        <DeviceStatus status={device.status} />
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4">
        <DeviceMetric label="Connection" value={device.connection} />
        <DeviceMetric label="IP address" value={device.ipAddress} />
        <DeviceMetric label="Firmware" value={device.firmwareVersion} />
        <DeviceMetric label="Temperature" value={`${device.temperature}°C`} />
      </dl>
      <div className="mt-5 rounded-lg bg-gray-50 p-3">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-gray-600">Device health</span>
          <span className="font-semibold text-gray-800">{device.health}%</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-200">
          <div className={`h-full rounded-full ${healthTone}`} style={{ width: `${device.health}%` }} />
        </div>
      </div>
      <DeviceActions deviceName={device.name} onAction={onAction} />
    </Card>
  );
}
