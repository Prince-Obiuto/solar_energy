import { BoltIcon, ClockIcon } from "@heroicons/react/24/outline";

import Card from "../../../components/ui/Card";
import AreaMetric from "./AreaMetric";
import BreakerStatus from "./BreakerStatus";

export default function AreaCard({ area }) {
  return (
    <Card className="border border-gray-100 p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-gray-900">{area.name}</p>
          <p className="mt-1 flex items-center gap-1 text-xs text-gray-500"><ClockIcon className="size-3.5" />Updated {area.lastUpdate}</p>
        </div>
        <BreakerStatus status={area.breakerStatus} />
      </div>
      <div className="mt-5 flex items-end justify-between rounded-xl bg-emerald-50 p-4">
        <div>
          <p className="text-xs font-medium text-emerald-700">Current Load</p>
          <p className="mt-1 text-2xl font-bold text-emerald-950">{area.currentLoad.toFixed(2)} <span className="text-sm">kW</span></p>
        </div>
        <BoltIcon className="size-8 text-emerald-600" />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <AreaMetric label="Today's energy" value={`${area.todayEnergy.toFixed(1)} kWh`} />
        <AreaMetric label="Voltage" value={`${area.voltage.toFixed(1)} V`} />
        <AreaMetric label="Current" value={`${area.current.toFixed(1)} A`} />
        <AreaMetric label="Power factor" value={area.powerFactor.toFixed(2)} />
      </div>
    </Card>
  );
}
