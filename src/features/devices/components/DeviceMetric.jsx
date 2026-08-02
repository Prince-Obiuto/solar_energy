export default function DeviceMetric({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="mt-1 truncate text-sm font-medium text-gray-700" title={value}>{value}</dd>
    </div>
  );
}
