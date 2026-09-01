import { ArrowDownTrayIcon, ArrowTrendingUpIcon, BanknotesIcon, BoltIcon } from "@heroicons/react/24/outline";

import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";

const STAT_CONFIG = [
  { key: "generated", label: "Generated", icon: ArrowTrendingUpIcon, tone: "text-emerald-600", suffix: "kWh" },
  { key: "consumed", label: "Consumed", icon: BoltIcon, tone: "text-sky-600", suffix: "kWh" },
  { key: "imported", label: "Grid Imported", icon: ArrowDownTrayIcon, tone: "text-teal-600", suffix: "kWh" },
  { key: "savings", label: "Savings", icon: BanknotesIcon, tone: "text-amber-600", prefix: "$" },
];

export default function TodayStatistics({ statistics }) {
  return (
    <Card>
      <SectionHeading eyebrow="24-hour summary" title="Today's Statistics" />
      <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
        {STAT_CONFIG.map(({ icon: Icon, key, label, prefix = "", suffix = "", tone }) => (
          <div className="rounded-lg bg-gray-50 p-3" key={key}>
            <Icon className={`size-4 ${tone}`} />
            <p className="mt-3 text-xl font-bold text-gray-900">{statistics[key] == null ? "--" : `${prefix}${statistics[key]} ${suffix}`}</p>
            <p className="mt-1 text-xs text-gray-500">{label}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}
