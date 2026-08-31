import { CheckCircleIcon } from "@heroicons/react/24/solid";

import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";

export default function SystemHealth({ items }) {
  return (
    <Card>
      <SectionHeading eyebrow="Component diagnostics" title="System Health" />
      <ul className="mt-5 space-y-4">
        {items.map((item) => (
          <li key={item.id}>
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-gray-700">{item.label}</span>
              <span className="flex items-center gap-1 text-xs font-medium text-emerald-700"><CheckCircleIcon className="size-4" />{item.value}</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-100">
              <div className="h-full rounded-full bg-emerald-500" style={{ width: `${item.score}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
