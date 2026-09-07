import { ArrowDownTrayIcon, ArrowTrendingUpIcon, BoltIcon } from "@heroicons/react/24/outline";

import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";
import { formatKilowattHours } from "../../../utils/formatters";

const STAT_CONFIG = [
  { key: "generated", label: "Solar Generated", icon: ArrowTrendingUpIcon, tone: "text-emerald-600" },
  { key: "consumed", label: "Energy Used", icon: BoltIcon, tone: "text-sky-600" },
  { key: "imported", label: "Grid Imported", icon: ArrowDownTrayIcon, tone: "text-teal-600" },
];

export default function TodayStatistics({ statistics }) {
  return (
    <Card>
      <SectionHeading eyebrow="24-hour summary" title="Today's Statistics" />
      <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
        {STAT_CONFIG.map(({ icon: Icon, key, label, tone }) => (
          <div className="rounded-lg bg-gray-50 p-3" key={key}>
            <Icon className={`size-4 ${tone}`} />
            <p className="mt-3 text-xl font-bold text-gray-900">{formatKilowattHours(statistics[key])}</p>
            <p className="mt-1 text-xs text-gray-500">{label}</p>
          </div>
        ))}
      </div>
      {statistics.coverage?.grid_import === "unavailable" && (
        <p className="mt-4 text-xs text-gray-500">Grid imported energy is unavailable until the Siseli GridPower direction is verified.</p>
      )}
    </Card>
  );
}
