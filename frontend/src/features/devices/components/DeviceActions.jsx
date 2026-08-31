import { ArrowPathIcon, Cog6ToothIcon, EyeIcon } from "@heroicons/react/24/outline";

const ACTIONS = [
  { label: "View", icon: EyeIcon },
  { label: "Restart", icon: ArrowPathIcon },
  { label: "Configure", icon: Cog6ToothIcon },
];

export default function DeviceActions({ deviceName, onAction }) {
  return (
    <div className="mt-5 flex gap-2 border-t border-gray-100 pt-4">
      {ACTIONS.map(({ icon: Icon, label }) => (
        <button className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-semibold text-gray-600 transition hover:bg-gray-100 hover:text-emerald-700" key={label} onClick={() => onAction(label, deviceName)} type="button">
          <Icon className="size-4" />
          {label}
        </button>
      ))}
    </div>
  );
}
