const STATUS_STYLES = {
  On: "bg-emerald-100 text-emerald-700",
  Off: "bg-gray-100 text-gray-600",
};

export default function BreakerStatus({ status }) {
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_STYLES[status]}`}>Breaker {status}</span>;
}
