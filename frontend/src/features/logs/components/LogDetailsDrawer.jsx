import { ClipboardDocumentIcon } from "@heroicons/react/24/outline";
import Drawer from "../../../components/ui/Drawer";
import Badge from "../../../components/ui/Badge";
import LogLevelIcon from "./LogLevelIcon";

const show = (value) => typeof value === "boolean" ? (value ? "ON" : "OFF") : value ?? "N/A";

export default function LogDetailsDrawer({ log, onClose }) {
  if (!log) return null;
  const details = [
    ["Actor", log.requested_by || log.actor], ["Role", log.role], ["Area", log.area],
    ["Device", log.device], ["Action", log.action], ["Previous state", show(log.previous_value)],
    ["Requested state", show(log.requested_value)], ["Verified state", show(log.verified_value)],
    ["Result", log.status || log.raw_status], ["Reason", log.reason],
    ["Requested", log.requested_at], ["Completed", log.completed_at], ["Timestamp", log.timestamp],
  ].filter(([, value]) => value != null);
  return <Drawer isOpen onClose={onClose} title="Log details"><div className="space-y-6"><div className="flex items-center gap-3"><LogLevelIcon level={log.level} /><Badge>{log.category}</Badge></div><div><h3 className="text-lg font-semibold text-gray-900">{log.title}</h3><p className="mt-2 text-sm leading-6 text-gray-600">{log.message}</p></div><dl className="grid gap-4 rounded-xl bg-gray-50 p-4 text-sm sm:grid-cols-2">{details.map(([label, value]) => <div key={label}><dt className="text-xs text-gray-500">{label}</dt><dd className="mt-1 font-medium text-gray-800">{String(value)}</dd></div>)}</dl><div className="flex items-center gap-2 text-xs text-gray-500"><ClipboardDocumentIcon className="size-4" />Persisted audit event — read only</div></div></Drawer>;
}
