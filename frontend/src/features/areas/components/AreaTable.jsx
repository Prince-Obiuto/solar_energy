import StatusChip from "../../../components/ui/StatusChip";
import Table from "../../../components/ui/Table";

const COLUMNS = [
  { key: "name", label: "Area", cellClassName: "whitespace-nowrap font-semibold text-gray-900" },
  { key: "breakerStatus", label: "Breaker", cellClassName: "whitespace-nowrap", render: (area) => <StatusChip status={area.breakerStatus}>Breaker {area.breakerStatus}</StatusChip> },
  { key: "currentLoad", label: "Current load", cellClassName: "whitespace-nowrap", render: (area) => `${area.currentLoad.toFixed(2)} kW` },
  { key: "todayEnergy", label: "Today", cellClassName: "whitespace-nowrap", render: (area) => `${area.todayEnergy.toFixed(1)} kWh` },
  { key: "voltage", label: "Voltage", cellClassName: "whitespace-nowrap", render: (area) => `${area.voltage.toFixed(1)} V` },
  { key: "current", label: "Current", cellClassName: "whitespace-nowrap", render: (area) => `${area.current.toFixed(1)} A` },
  { key: "powerFactor", label: "Power factor", cellClassName: "whitespace-nowrap", render: (area) => area.powerFactor.toFixed(2) },
  { key: "lastUpdate", label: "Last update", cellClassName: "whitespace-nowrap text-gray-500" },
];

export default function AreaTable({ areas }) {
  return <Table columns={COLUMNS} data={areas} tableClassName="min-w-[960px]" />;
}
