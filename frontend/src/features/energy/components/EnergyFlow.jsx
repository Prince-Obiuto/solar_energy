import { Battery100Icon, CpuChipIcon, HomeModernIcon, SunIcon } from "@heroicons/react/24/outline";

import { PowerFlowDiagram } from "../../../components/charts";
import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";
import { formatKilowatts, formatPercentage } from "../../../utils/formatters";

function GridTowerIcon(props) {
  return (
    <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" viewBox="0 0 24 24" {...props}>
      <path d="M12 2 8 22m4-20 4 20M9.7 8h4.6M7.8 14h8.4M5 21h14M8 14l-3 7m11-7 3 7" />
    </svg>
  );
}

export default function EnergyFlow({ data }) {
  const nodes = {
    solar: { active: data.solar.power > 0, detail: data.solar.status || "Status unavailable", icon: SunIcon, label: "PV Array", status: data.solar.status ? "online" : "unknown", tone: "bg-amber-100 text-amber-600", value: formatKilowatts(data.solar.power) },
    battery: { active: data.battery.power != null && data.battery.power !== 0, detail: data.battery.state || "State unavailable", icon: Battery100Icon, label: "Battery", reverse: data.battery.charging, status: data.battery.state ? "online" : "unknown", tone: "bg-violet-100 text-violet-600", value: formatPercentage(data.battery.percentage) },
    inverter: { detail: `Hybrid · ${data.inverter.status || "Unknown"}`, icon: CpuChipIcon, label: "Inverter", status: data.inverter.status?.toLowerCase() || "unknown", tone: "bg-emerald-100 text-emerald-600", value: formatKilowatts(data.inverter.outputPower) },
    loads: { active: data.loads.totalPower > 0, detail: "Consuming", icon: HomeModernIcon, label: "Site Loads", status: "online", tone: "bg-sky-100 text-sky-600", value: formatKilowatts(data.loads.totalPower) },
    grid: { active: data.grid.connected && data.grid.power !== 0, detail: data.grid.connected == null ? "Status unavailable" : data.grid.connected ? "Available" : "Unavailable", icon: GridTowerIcon, label: "Utility Grid", reverse: true, status: data.grid.connected == null ? "unknown" : data.grid.connected ? "online" : "offline", tone: "bg-teal-100 text-teal-600", value: formatKilowatts(data.grid.power) },
  };

  return (
    <Card>
      <SectionHeading action={<span className="inline-flex items-center gap-2 text-xs font-medium text-emerald-700"><span className="size-2 animate-pulse rounded-full bg-emerald-500 motion-reduce:animate-none" />Live</span>} eyebrow="Real-time overview" title="Live Energy Flow" />
      <PowerFlowDiagram className="mx-auto mt-6 max-w-3xl" nodes={nodes} />
      <dl className="mt-6 grid grid-cols-2 gap-3 border-t border-gray-100 pt-5 sm:grid-cols-4">
        <div className="rounded-lg bg-gray-50 p-3"><dt className="text-xs text-gray-500">Grid connection</dt><dd className="mt-1 text-sm font-semibold text-gray-800">{data.grid.connected == null ? "--" : data.grid.connected ? "Connected" : "Disconnected"}</dd></div>
        <div className="rounded-lg bg-gray-50 p-3"><dt className="text-xs text-gray-500">Grid import</dt><dd className="mt-1 text-sm font-semibold text-gray-800">{formatKilowatts(data.grid.importPower)}</dd></div>
        <div className="rounded-lg bg-gray-50 p-3"><dt className="text-xs text-gray-500">Grid voltage</dt><dd className="mt-1 text-sm font-semibold text-gray-800">{data.grid.voltage == null ? "--" : `${data.grid.voltage} V`}</dd></div>
        <div className="rounded-lg bg-gray-50 p-3"><dt className="text-xs text-gray-500">Grid frequency</dt><dd className="mt-1 text-sm font-semibold text-gray-800">{data.grid.frequency == null ? "--" : `${data.grid.frequency} Hz`}</dd></div>
      </dl>
    </Card>
  );
}
