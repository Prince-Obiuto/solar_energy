import { MagnifyingGlassIcon, Squares2X2Icon, TableCellsIcon } from "@heroicons/react/24/outline";

const VIEW_OPTIONS = [
  { id: "cards", label: "Card view", icon: Squares2X2Icon },
  { id: "table", label: "Table view", icon: TableCellsIcon },
];

export default function AreaFilters({ onQueryChange, onStatusChange, onViewChange, query, status, view }) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-gray-100 bg-white p-3 shadow-sm sm:flex-row sm:items-center">
      <label className="relative min-w-0 flex-1">
        <span className="sr-only">Search areas</span>
        <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-gray-400" />
        <input className="w-full rounded-lg border border-gray-200 py-2 pl-10 pr-3 text-sm text-gray-800 outline-none transition placeholder:text-gray-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100" onChange={(event) => onQueryChange(event.target.value)} placeholder="Search areas" type="search" value={query} />
      </label>
      <label>
        <span className="sr-only">Filter by breaker status</span>
        <select className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 sm:w-auto" onChange={(event) => onStatusChange(event.target.value)} value={status}>
          <option value="all">All breakers</option>
          <option value="on">Breaker on</option>
          <option value="off">Breaker off</option>
        </select>
      </label>
      <div className="flex rounded-lg border border-gray-200 p-1" role="group" aria-label="Select view">
        {VIEW_OPTIONS.map(({ icon: Icon, id, label }) => (
          <button aria-label={label} className={`rounded-md p-2 transition ${view === id ? "bg-emerald-600 text-white" : "text-gray-500 hover:bg-gray-100"}`} key={id} onClick={() => onViewChange(id)} type="button">
            <Icon className="size-4" />
          </button>
        ))}
      </div>
    </div>
  );
}
