import { ArrowDownTrayIcon, DocumentArrowDownIcon, PrinterIcon } from "@heroicons/react/24/outline";

const ACTIONS = [
  { label: "Export CSV", icon: ArrowDownTrayIcon },
  { label: "Export PDF", icon: DocumentArrowDownIcon },
  { label: "Print", icon: PrinterIcon },
];

export default function ReportToolbar({ onAction }) {
  return (
    <div className="flex flex-wrap gap-2">
      {ACTIONS.map(({ icon: Icon, label }) => (
        <button className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-700 shadow-sm transition hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-800" key={label} onClick={() => onAction(label)} type="button">
          <Icon className="size-4" />
          {label}
        </button>
      ))}
    </div>
  );
}
