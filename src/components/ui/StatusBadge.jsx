const STATUS_STYLES = {
  connected: "bg-green-100 text-green-800",
  disconnected: "bg-gray-100 text-gray-700",
  online: "bg-green-100 text-green-800",
  offline: "bg-gray-100 text-gray-700",
};

export default function StatusBadge({ status }) {
  const normalizedStatus = status.toLowerCase();
  const style = STATUS_STYLES[normalizedStatus] ?? STATUS_STYLES.offline;

  return <span className={`rounded-full px-3 py-1 text-sm font-medium ${style}`}>{status}</span>;
}
