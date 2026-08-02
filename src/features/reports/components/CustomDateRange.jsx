export default function CustomDateRange() {
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-sky-100 bg-sky-50 p-4">
      <label className="text-sm font-medium text-sky-900">From<input className="mt-1 block rounded-lg border border-sky-200 bg-white px-3 py-2 text-sm text-gray-700" defaultValue="2026-07-01" type="date" /></label>
      <label className="text-sm font-medium text-sky-900">To<input className="mt-1 block rounded-lg border border-sky-200 bg-white px-3 py-2 text-sm text-gray-700" defaultValue="2026-07-31" type="date" /></label>
      <p className="pb-2 text-xs text-sky-700">Date selection is a visual placeholder.</p>
    </div>
  );
}
