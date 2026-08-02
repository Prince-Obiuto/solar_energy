import { CheckCircleIcon, ExclamationTriangleIcon, InformationCircleIcon } from "@heroicons/react/24/solid";

import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";

const ALERT_STYLES = {
  success: { icon: CheckCircleIcon, tone: "text-emerald-500" },
  warning: { icon: ExclamationTriangleIcon, tone: "text-amber-500" },
  info: { icon: InformationCircleIcon, tone: "text-sky-500" },
};

export default function RecentAlerts({ alerts }) {
  return (
    <Card className="border border-gray-100 shadow-sm">
      <SectionHeading action={<button className="text-sm font-medium text-emerald-700 hover:text-emerald-800" type="button">View all</button>} eyebrow="Notifications" title="Recent Alerts" />
      <ul className="mt-4 divide-y divide-gray-100">
        {alerts.map(({ detail, id, severity, time, title }) => {
          const { icon: Icon, tone } = ALERT_STYLES[severity];
          return (
            <li className="flex gap-3 py-3 first:pt-0 last:pb-0" key={id}>
              <Icon className={`mt-0.5 size-5 shrink-0 ${tone}`} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-800">{title}</p>
                <p className="mt-0.5 truncate text-xs text-gray-500">{detail}</p>
              </div>
              <time className="shrink-0 text-xs text-gray-400">{time}</time>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
