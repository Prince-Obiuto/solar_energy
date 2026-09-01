import { BoltIcon, CircleStackIcon, CpuChipIcon, ServerStackIcon, SignalIcon } from "@heroicons/react/24/outline";

const ICONS = {
  inverter: BoltIcon,
  battery: CircleStackIcon,
  breakers: CpuChipIcon,
  server: ServerStackIcon,
  switch: SignalIcon,
};

export default function DeviceIcon({ type }) {
  const Icon = ICONS[type] || CpuChipIcon;
  return <span className="grid size-11 place-items-center rounded-xl bg-emerald-100 text-emerald-700"><Icon className="size-6" /></span>;
}
