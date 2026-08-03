import { ClipboardDocumentIcon, XMarkIcon } from "@heroicons/react/24/outline";

import LogLevelIcon from "./LogLevelIcon";

export default function LogDetailsDrawer({ log, onClose }) {
  if (!log) return null;

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-labelledby="log-details-title">
      <button aria-label="Close log details" className="absolute inset-0 bg-gray-950/40" onClick={onClose} type="button" />
      <aside className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-200 p-5"><div className="flex items-center gap-3"><LogLevelIcon level={log.level} /><h2 className="font-semibold text-gray-900" id="log-details-title">Log details</h2></div><button aria-label="Close log details" className="rounded-lg p-1 text-gray-400 hover:bg-gray-100" onClick={onClose} type="button"><XMarkIcon className="size-5" /></button></div>
        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          <div><span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600">{log.category}</span><h3 className="mt-3 text-lg font-semibold text-gray-900">{log.title}</h3><p className="mt-2 text-sm leading-6 text-gray-600">{log.message}</p></div>
          <dl className="space-y-4 rounded-xl bg-gray-50 p-4 text-sm"><div><dt className="text-xs text-gray-500">Timestamp</dt><dd className="mt-1 font-medium text-gray-800">{log.timestamp}</dd></div><div><dt className="text-xs text-gray-500">Actor</dt><dd className="mt-1 font-medium text-gray-800">{log.actor}</dd></div><div><dt className="text-xs text-gray-500">Source</dt><dd className="mt-1 font-medium text-gray-800">{log.source}</dd></div></dl>
          <div className="flex items-center gap-2 text-xs text-gray-500"><ClipboardDocumentIcon className="size-4" />Mock audit log — read only</div>
        </div>
      </aside>
    </div>
  );
}
