import { ChevronRightIcon } from "@heroicons/react/24/outline";

import LogLevelIcon from "./LogLevelIcon";

export default function LogTimelineItem({ log, onSelect }) {
  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      <div className="relative z-10 grid size-9 shrink-0 place-items-center rounded-full bg-white ring-4 ring-gray-50"><LogLevelIcon level={log.level} /></div>
      <div className="min-w-0 flex-1 rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div><span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600">{log.category}</span><h3 className="mt-2 text-sm font-semibold text-gray-900">{log.title}</h3><p className="mt-1 text-sm text-gray-500">{log.message}</p></div>
          <time className="shrink-0 text-xs text-gray-400">{log.timestamp}</time>
        </div>
        <button className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:text-emerald-800" onClick={() => onSelect(log)} type="button">View details <ChevronRightIcon className="size-4" /></button>
      </div>
    </li>
  );
}
