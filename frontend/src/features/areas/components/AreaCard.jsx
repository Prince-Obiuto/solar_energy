import { BoltIcon, ClockIcon } from "@heroicons/react/24/outline";

import Card from "../../../components/ui/Card";
import StatusChip from "../../../components/ui/StatusChip";
import AreaMetric from "./AreaMetric";
import { formatMeasurement, formatRelativeTime } from "../../../utils/formatters";

export default function AreaCard({ area }) {
  return (
    <Card padding="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-gray-900">{area.name}</p>
          <p className={`mt-1 flex items-center gap-1 text-xs ${area.stale ? "text-amber-600" : "text-gray-500"}`}><ClockIcon className="size-3.5" />Updated {formatRelativeTime(area.lastSeen)}{area.stale ? " · stale" : ""}</p>
        </div>
        <StatusChip status={area.breakerStatus}>Breaker {area.breakerStatus}</StatusChip>
      </div>
      <div className="mt-5 flex items-end justify-between rounded-xl bg-emerald-50 p-4">
        <div>
          <p className="text-xs font-medium text-emerald-700">Current Load</p>
          <p className="mt-1 text-2xl font-bold text-emerald-950">{formatMeasurement(area.currentLoad, "kW", 2)}</p>
        </div>
        <BoltIcon className="size-8 text-emerald-600" />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <AreaMetric label="Accumulated energy" value={area.capabilities.energy_total ? formatMeasurement(area.accumulatedEnergy, "", 1) : "N/A"} />
        <AreaMetric label="Voltage" value={area.capabilities.voltage ? formatMeasurement(area.voltage, "V") : "N/A"} />
        <AreaMetric label="Current" value={area.capabilities.current ? formatMeasurement(area.current, "A") : "N/A"} />
        <AreaMetric label="Configuration" value={area.capabilities.remote_configuration ? (area.configuration ? "Available" : "--") : "N/A"} />
      </div>
    </Card>
  );
}
