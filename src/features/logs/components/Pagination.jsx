import { ChevronLeftIcon, ChevronRightIcon } from "@heroicons/react/24/outline";

export default function Pagination({ currentPage, onPageChange, totalItems, totalPages }) {
  return (
    <div className="flex flex-col gap-3 border-t border-gray-100 pt-4 text-sm sm:flex-row sm:items-center sm:justify-between"><p className="text-gray-500">{totalItems} matching log entries</p><div className="flex items-center gap-2"><button aria-label="Previous page" className="rounded-lg border border-gray-200 p-2 text-gray-600 disabled:cursor-not-allowed disabled:opacity-40" disabled={currentPage === 1} onClick={() => onPageChange(currentPage - 1)} type="button"><ChevronLeftIcon className="size-4" /></button><span className="text-xs font-medium text-gray-600">Page {currentPage} of {totalPages}</span><button aria-label="Next page" className="rounded-lg border border-gray-200 p-2 text-gray-600 disabled:cursor-not-allowed disabled:opacity-40" disabled={currentPage === totalPages} onClick={() => onPageChange(currentPage + 1)} type="button"><ChevronRightIcon className="size-4" /></button></div></div>
  );
}
