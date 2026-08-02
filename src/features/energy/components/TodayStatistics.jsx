import { ArrowTrendingDownIcon, ArrowTrendingUpIcon, BanknotesIcon, BoltIcon } from "@heroicons/react/24/outline";

import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";

const STAT_CONFIG = [
  { key: "generated", label: "Generated", icon: ArrowTrendingUpIcon, tone: "text-emerald-600", suffix: "kWh" },
  { key: "consumed", label: "Consumed", icon: BoltIcon, tone: "text-sky-600", suffix: "kWh" },
  { key: "exported", label: "Exported", icon: ArrowTrendingDownIcon, tone: "text-violet-600", suffix: "kWh" },
  { key: "savings", label: "Savings", icon: BanknotesIcon, tone: "text-amber-600", prefix: "$" },
];

export default function TodayStatistics({ statistics }) {
  return (
    <Card className="border border-gray-100 shadow-sm">
      <SectionHeading eyebrow="24-hour summary" title="Today's Statistics" />
      <div className="mt-5 grid grid-cols-2 gap-4">
        {STAT_CONFIG.map(({ icon: Icon, key, label, prefix = "", suffix = "" }) => (
          <div className="rounded-lg bg-gray-50 p-3" key={key}>
            <Icon className="size-4 text-gray-400" />
            <p className="mt-3 text-xl font-bold text-gray-900">{prefix}{statistics[key]} {suffix}</p>
            <p className="mt-1 text-xs text-gray-500">{label}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}
