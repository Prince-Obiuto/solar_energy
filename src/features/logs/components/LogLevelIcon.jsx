import { CheckCircleIcon, ExclamationTriangleIcon, InformationCircleIcon, XCircleIcon } from "@heroicons/react/24/solid";

const ICONS = {
  error: { icon: XCircleIcon, tone: "text-rose-500" },
  info: { icon: InformationCircleIcon, tone: "text-sky-500" },
  success: { icon: CheckCircleIcon, tone: "text-emerald-500" },
  warning: { icon: ExclamationTriangleIcon, tone: "text-amber-500" },
};

export default function LogLevelIcon({ level }) {
  const { icon: Icon, tone } = ICONS[level];
  return <Icon className={`size-5 ${tone}`} />;
}
