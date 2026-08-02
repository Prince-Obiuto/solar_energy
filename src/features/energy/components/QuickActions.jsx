import { AdjustmentsHorizontalIcon, ArrowPathIcon, DocumentChartBarIcon } from "@heroicons/react/24/outline";

import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";

const ACTIONS = [
  { label: "Refresh data", icon: ArrowPathIcon },
  { label: "View controls", icon: AdjustmentsHorizontalIcon },
  { label: "Generate report", icon: DocumentChartBarIcon },
];

export default function QuickActions({ onRefresh }) {
  return (
    <Card className="border border-gray-100 shadow-sm">
      <SectionHeading eyebrow="Shortcuts" title="Quick Actions" />
      <div className="mt-5 grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
        {ACTIONS.map(({ icon: Icon, label }) => (
          <button
            className="flex items-center gap-3 rounded-lg border border-gray-200 px-3 py-3 text-left text-sm font-medium text-gray-700 transition hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-800"
            key={label}
            onClick={label === "Refresh data" ? onRefresh : undefined}
            type="button"
          >
            <Icon className="size-5 text-emerald-600" />
            {label}
          </button>
        ))}
      </div>
    </Card>
  );
}
