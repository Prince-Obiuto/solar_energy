const STATUS_STYLES = {
  Online: "bg-emerald-100 text-emerald-700",
  Warning: "bg-amber-100 text-amber-700",
  Offline: "bg-gray-100 text-gray-600",
};

export default function DeviceStatus({ status }) {
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_STYLES[status]}`}>{status}</span>;
}
