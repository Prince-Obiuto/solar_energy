export default function UserStatus({ status }) {
  const styles = status === "Active" ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-600";
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${styles}`}>{status}</span>;
}
