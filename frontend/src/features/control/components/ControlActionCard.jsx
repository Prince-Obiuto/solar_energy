import { ArrowRightIcon } from "@heroicons/react/24/outline";

import Card from "../../../components/ui/Card";

const TONE_STYLES = {
  danger: "bg-rose-100 text-rose-700 ring-rose-200 hover:border-rose-300",
  neutral: "bg-sky-100 text-sky-700 ring-sky-200 hover:border-sky-300",
  success: "bg-emerald-100 text-emerald-700 ring-emerald-200 hover:border-emerald-300",
  warning: "bg-amber-100 text-amber-700 ring-amber-200 hover:border-amber-300",
};

export default function ControlActionCard({ action, onSelect }) {
  const Icon = action.icon;
  const tone = TONE_STYLES[action.tone];

  return (
    <Card className={`border border-gray-100 p-5 shadow-sm transition ${tone.split(" ").at(-1)}`}>
      <span className={`grid size-11 place-items-center rounded-xl ${tone.split(" ").slice(0, 2).join(" ")}`}>
        <Icon className="size-6" />
      </span>
      <h3 className="mt-4 font-semibold text-gray-900">{action.label}</h3>
      <p className="mt-1 min-h-10 text-sm leading-5 text-gray-500">{action.description}</p>
      <button className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-gray-700 transition hover:text-emerald-700" onClick={() => onSelect(action)} type="button">
        Review action <ArrowRightIcon className="size-4" />
      </button>
    </Card>
  );
}
