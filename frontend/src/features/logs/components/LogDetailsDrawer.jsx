import { ClipboardDocumentIcon } from "@heroicons/react/24/outline";

import Drawer from "../../../components/ui/Drawer";
import Badge from "../../../components/ui/Badge";
import LogLevelIcon from "./LogLevelIcon";

export default function LogDetailsDrawer({ log, onClose }) {
  if (!log) return null;

  return <Drawer isOpen onClose={onClose} title="Log details"><div className="space-y-6"><div className="flex items-center gap-3"><LogLevelIcon level={log.level} /><Badge>{log.category}</Badge></div><div><h3 className="text-lg font-semibold text-gray-900">{log.title}</h3><p className="mt-2 text-sm leading-6 text-gray-600">{log.message}</p></div><dl className="space-y-4 rounded-xl bg-gray-50 p-4 text-sm"><div><dt className="text-xs text-gray-500">Timestamp</dt><dd className="mt-1 font-medium text-gray-800">{log.timestamp}</dd></div><div><dt className="text-xs text-gray-500">Actor</dt><dd className="mt-1 font-medium text-gray-800">{log.actor}</dd></div><div><dt className="text-xs text-gray-500">Source</dt><dd className="mt-1 font-medium text-gray-800">{log.source}</dd></div></dl><div className="flex items-center gap-2 text-xs text-gray-500"><ClipboardDocumentIcon className="size-4" />Mock audit log — read only</div></div></Drawer>;
}
