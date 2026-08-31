import { Battery100Icon } from "@heroicons/react/24/outline";

export default function BatteryIndicator({ className = "", label = "Battery", percentage, status = "Healthy" }) {
  const safePercentage = Math.min(Math.max(percentage, 0), 100);
  const tone = safePercentage > 25 ? "bg-emerald-500" : "bg-rose-500";
  return <div className={`rounded-xl border border-gray-100 bg-white p-4 shadow-sm ${className}`}><div className="flex items-center justify-between"><span className="text-sm font-semibold text-gray-800">{label}</span><Battery100Icon className="size-5 text-gray-400" /></div><div className="mt-4 flex items-end gap-3"><p className="text-3xl font-bold text-gray-900">{safePercentage}%</p><span className="mb-1 text-xs text-gray-500">{status}</span></div><div className="mt-3 h-3 overflow-hidden rounded-full bg-gray-100"><div className={`h-full rounded-full ${tone}`} style={{ width: `${safePercentage}%` }} /></div></div>;
}
