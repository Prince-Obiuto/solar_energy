import { MagnifyingGlassIcon } from "@heroicons/react/24/outline";

import { LOG_CATEGORIES } from "../services/log.service";

export default function LogFilters({ category, level, onCategoryChange, onLevelChange, onQueryChange, query }) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-gray-100 bg-white p-3 shadow-sm lg:flex-row lg:items-center">
      <label className="relative min-w-0 flex-1"><span className="sr-only">Search logs</span><MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-gray-400" /><input className="w-full rounded-lg border border-gray-200 py-2 pl-10 pr-3 text-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100" onChange={(event) => onQueryChange(event.target.value)} placeholder="Search activity logs" type="search" value={query} /></label>
      <select aria-label="Filter by category" className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none focus:border-emerald-500" onChange={(event) => onCategoryChange(event.target.value)} value={category}><option value="all">All categories</option>{LOG_CATEGORIES.map((item) => <option key={item} value={item}>{item}</option>)}</select>
      <select aria-label="Filter by level" className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none focus:border-emerald-500" onChange={(event) => onLevelChange(event.target.value)} value={level}><option value="all">All levels</option><option value="info">Information</option><option value="success">Success</option><option value="warning">Warning</option><option value="error">Error</option></select>
    </div>
  );
}
