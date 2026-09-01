import StatusChip from "../../../components/ui/StatusChip";
import Table from "../../../components/ui/Table";
import { formatMeasurement, formatRelativeTime } from "../../../utils/formatters";

const COLUMNS = [
  { key: "name", label: "Area", cellClassName: "whitespace-nowrap font-semibold text-gray-900" },
  { key: "breakerStatus", label: "Breaker", cellClassName: "whitespace-nowrap", render: (area) => <StatusChip status={area.breakerStatus}>Breaker {area.breakerStatus}</StatusChip> },
  { key: "currentLoad", label: "Current load", cellClassName: "whitespace-nowrap", render: (area) => formatMeasurement(area.currentLoad, "kW", 2) },
  { key: "accumulatedEnergy", label: "Accumulated energy", cellClassName: "whitespace-nowrap", render: (area) => area.capabilities.energy_total ? formatMeasurement(area.accumulatedEnergy, "", 1) : "N/A" },
  { key: "voltage", label: "Voltage", cellClassName: "whitespace-nowrap", render: (area) => area.capabilities.voltage ? formatMeasurement(area.voltage, "V") : "N/A" },
  { key: "current", label: "Current", cellClassName: "whitespace-nowrap", render: (area) => area.capabilities.current ? formatMeasurement(area.current, "A") : "N/A" },
  { key: "lastSeen", label: "Last update", cellClassName: "whitespace-nowrap text-gray-500", render: (area) => `${formatRelativeTime(area.lastSeen)}${area.stale ? " · stale" : ""}` },
];

export default function AreaTable({ areas }) {
  return <Table columns={COLUMNS} data={areas} tableClassName="min-w-[960px]" />;
}
